"""Verifier orchestrator: runs every verification gate for one component."""

import ast
import contextlib
import dataclasses
import hashlib
import importlib.util
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from collections.abc import Mapping
from pathlib import Path

GATE_VERSION = "verifier-orchestrator@2.3.0"

TIMEOUT = 300
_COMPARE_ENV = "HOTDOCS_VERIFY_COMPARE"
_RETRYABLE = ("network", "timeout", "rate_limit")
_USAGE = "usage: hotdocs verify-component <component-id> [--repo-root=<dir>] [--format=json|text]"

_CONFTEST = '''import json
import os


def pytest_assertrepr_compare(op, left, right):
    path = os.environ.get("HOTDOCS_VERIFY_COMPARE")
    if path and not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as handle:
            json.dump({"op": op, "left": repr(left), "right": repr(right)}, handle)
    return None
'''


@dataclasses.dataclass
class VerificationReport:
    component_id: str
    criteria: list
    requirement_results: dict
    interface_drift: bool
    mutation_score: float | None
    mutation_error: str | None
    overall: str

    def to_dict(self):
        return dataclasses.asdict(self)


def _get(obj, key, default=None):
    if isinstance(obj, Mapping):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _test_filename(criterion_id):
    return "test_" + criterion_id.lower().replace("-", "_") + ".py"


def _detail(message, expected=None, actual=None):
    return {"message": message, "expected": expected, "actual": actual}


def _literal(text):
    try:
        return ast.literal_eval(text)
    except Exception:
        return None


# ---------------------------------------------------------------- loading


def _load_module(base, name):
    flat = base / f"{name}.py"
    path = flat if flat.is_file() else base / name / "__init__.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _tool_root():
    here = Path(__file__).resolve()
    return next(p for p in here.parents if p.name == "gen").parent


def _load_dependency(root, rel, name):
    base = root / rel
    if not base.is_dir():
        base = _tool_root() / rel
    return _load_module(base, name)


# ---------------------------------------------------------------- corpus


def _frontmatter(path):
    text = path.read_text(encoding="utf-8")
    block = re.match(r"---\n(.*?)\n---", text, re.S).group(1)
    return {k: v.strip() for k, v in re.findall(r"^(\w+):[ \t]*(.*)$", block, re.M)}


def _read_criteria(acceptance_dir):
    specs = []
    for path in sorted(acceptance_dir.glob("AC-*.md")):
        text = path.read_text(encoding="utf-8")
        cid = re.search(r"^#\s+(AC-\S+)", text, re.M).group(1)
        cov = re.search(r"Covers:\s*`?([^\s`]+)", text)
        kind = re.compile(r"^Kind:\s*(\S+)", re.M).search(text, cov.end()).group(1)
        specs.append({
            "id": cid,
            "covers": cov.group(1),
            "kind": kind,
            "freeform": not re.search(r"^\s*```gherkin", text, re.M),
        })
    return specs


# ---------------------------------------------------------------- running


def _pytest(files, cwd, pythonpath, timeout, env_extra, extra_args=()):
    cmd = [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", *extra_args, *map(str, files)]
    env = {**os.environ, "PYTHONPATH": str(pythonpath), "PYTHONDONTWRITEBYTECODE": "1", **env_extra}
    start = time.monotonic()
    proc = subprocess.Popen(
        cmd, cwd=str(cwd), env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, start_new_session=True,
    )
    try:
        out, _ = proc.communicate(timeout=timeout)
        rc = proc.returncode
    except subprocess.TimeoutExpired:
        with contextlib.suppress(ProcessLookupError):
            os.killpg(proc.pid, signal.SIGKILL)
        proc.communicate()
        out, rc = "", None
    return rc, out, time.monotonic() - start


def _run_test(content, criterion_id, cwd, pythonpath):
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        (tmp / "conftest.py").write_text(_CONFTEST, encoding="utf-8")
        test = tmp / _test_filename(criterion_id)
        test.write_text(content, encoding="utf-8")
        record = tmp / "compare.json"
        rc, out, _ = _pytest([test], cwd, pythonpath, TIMEOUT, {_COMPARE_ENV: str(record)})
        if rc == 0:
            return None
        if rc is None:
            return _detail(f"timed out after {TIMEOUT} seconds")
        compared = json.loads(record.read_text(encoding="utf-8")) if record.is_file() else {}
        lines = out.splitlines()
        messages = (
            [line[1:].strip() for line in lines if line.startswith("E ")]
            or [line.strip() for line in reversed(lines) if line.strip()]
            or [f"pytest exited {rc}"]
        )
        return _detail(messages[0], _literal(compared.get("right")), _literal(compared.get("left")))


def _characterize(root, slug, code_dir):
    files = sorted((root / "verification" / slug).glob("test_*.py"))
    if not files:
        return []
    with tempfile.TemporaryDirectory() as tmp:
        report = Path(tmp) / "junit.xml"
        rc, _, _ = _pytest(files, root, code_dir, TIMEOUT, {}, [f"--junitxml={report}"])
        if rc is None:
            return None
        cases = []
        for case in ET.parse(report).iter("testcase"):
            bad = next((c for c in case if c.tag in ("failure", "error", "skipped")), None)
            message = None if bad is None else (bad.get("message") or bad.tag)
            cases.append((case.get("name", "").split("[")[0], message))
        return cases


def _sealed_detail(cases, criterion_id):
    if cases is None:
        return _detail(f"timed out after {TIMEOUT} seconds")
    prefix = "test_" + criterion_id.lower().replace("-", "_")
    matches = [msg for name, msg in cases if name == prefix or name.startswith(prefix + "_")]
    if not matches:
        return _detail("no characterization test")
    failed = [m for m in matches if m is not None]
    return _detail(failed[0]) if failed else None


# ---------------------------------------------------------------- drift


def _documented(text):
    sigs = []
    in_fence = False
    buffer = ""
    for line in text.splitlines():
        if re.match(r"^```\s*$", line) or (line.startswith("```") and not in_fence):
            plain = re.match(r"^```\s*$", line) is not None
            in_fence = plain and not in_fence
            buffer = ""
            continue
        if not in_fence:
            continue
        if buffer or re.match(r"[A-Za-z_]\w*\(", line):
            buffer += " " + line
            if buffer.count("(") <= buffer.count(")"):
                sigs.append(_signature(buffer))
                buffer = ""
    return sigs


def _signature(text):
    m = re.match(r"\s*([A-Za-z_]\w*)\(", text)
    depth = 0
    end = len(text)
    for i in range(m.end() - 1, len(text)):
        depth += text[i] in "([{"
        depth -= text[i] in ")]}"
        if depth == 0:
            end = i
            break
    params, current, depth = [], "", 0
    for c in text[m.end():end] + ",":
        depth += c in "([{"
        depth -= c in ")]}"
        if c == "," and depth == 0:
            params.append(current)
            current = ""
        else:
            current += c
    names = [p.group(1) for p in (re.match(r"\s*\*{0,2}([A-Za-z_]\w*)", q) for q in params) if p]
    return m.group(1), names


def _param_names(obj):
    try:
        import inspect
        return list(inspect.signature(obj).parameters)
    except (TypeError, ValueError):
        return None


def _interface_drift(comp_dir, code_dir, slug):
    sigs = []
    for name in ("library.md", "cli.md"):
        path = comp_dir / "interface" / name
        if path.is_file():
            sigs += _documented(path.read_text(encoding="utf-8"))
    if (comp_dir / "interface" / "cli.md").is_file():
        sigs.append(("main", None))
    if not sigs:
        return False
    try:
        module = _load_module(code_dir, slug.replace("-", "_"))
    except Exception:
        module = None
    for name, params in sigs:
        obj = getattr(module, name, None)
        if not callable(obj):
            return True
        if params is not None and _param_names(obj) != params:
            return True
    return False


# ---------------------------------------------------------------- mutation

_CMP = {
    ast.Eq: ast.NotEq, ast.NotEq: ast.Eq, ast.Lt: ast.GtE, ast.GtE: ast.Lt,
    ast.Gt: ast.LtE, ast.LtE: ast.Gt, ast.Is: ast.IsNot, ast.IsNot: ast.Is,
    ast.In: ast.NotIn, ast.NotIn: ast.In,
}
_BOOL = {ast.And: ast.Or, ast.Or: ast.And}
_BIN = {
    ast.Add: ast.Sub, ast.Sub: ast.Add, ast.Mult: ast.Div, ast.Div: ast.Mult,
    ast.FloorDiv: ast.Mod, ast.Mod: ast.FloorDiv,
}

_JS_RE = re.compile(r"\bfunction\s*[\w$]*\s*\(|=>|\b(const|let)\s")
_SCRIPT_RE = re.compile(r"<script[^>]*>(.*?)</script>", re.S)
_JS_WORD = re.compile(r"[A-Za-z_$][\w$]*|\d[\w.]*")
_JS_PUNCT = sorted(
    [">>>=", "===", "!==", ">>>", "<<=", ">>=", "**=", "...", "&&=", "||=", "??=",
     "=>", "==", "!=", "<=", ">=", "&&", "||", "??", "++", "--", "+=", "-=", "*=",
     "/=", "%=", "&=", "|=", "^=", "<<", ">>", "**", "?."],
    key=len, reverse=True,
)
_JS_SWAP = {
    "===": "!==", "!==": "===", "==": "!=", "!=": "==", "<": ">=", ">": "<=",
    "<=": ">", ">=": "<", "&&": "||", "||": "&&", "true": "false", "false": "true",
}


def _js_token_sites(s, a, b):
    sites, prev, i = [], None, a
    while i < b:
        c = s[i]
        if c.isspace():
            i += 1
        elif s.startswith("//", i, b):
            j = s.find("\n", i, b)
            i = b if j < 0 else j
        elif s.startswith("/*", i, b):
            j = s.find("*/", i + 2, b)
            i = b if j < 0 else j + 2
        elif c in "'\"`":
            j = i + 1
            while j < b and s[j] != c:
                j += 2 if s[j] == "\\" else 1
            i, prev = j + 1, "string"
        else:
            m = _JS_WORD.match(s, i, b)
            if m:
                tok, kind = m.group(), "word"
            else:
                tok = next((p for p in _JS_PUNCT if s.startswith(p, i, b)), c)
                kind = tok
            end = i + len(tok)
            if tok in _JS_SWAP:
                sites.append((i, end, _JS_SWAP[tok]))
            elif tok in ("+", "-") and prev in ("word", ")", "]"):
                sites.append((i, end, "-" if tok == "+" else "+"))
            prev, i = kind, end
    return sites


def _js_sites(s):
    if not (_JS_RE.search(s) and (";" in s or "{" in s)):
        return []
    spans = [m.span(1) for m in _SCRIPT_RE.finditer(s)] if "<script" in s else [(0, len(s))]
    sites = []
    for a, b in spans:
        sites.extend(_js_token_sites(s, a, b))
    return sites


def _sites(tree):
    docs = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            first = node.body[:1]
            if first and isinstance(first[0], ast.Expr) and isinstance(first[0].value, ast.Constant) \
                    and isinstance(first[0].value.value, str):
                docs.add(id(first[0].value))
    sites = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare) and len(node.ops) == 1:
            sites.append((node, "ops", [_CMP[type(node.ops[0])]()]))
        elif isinstance(node, ast.BoolOp):
            sites.append((node, "op", _BOOL[type(node.op)]()))
        elif isinstance(node, ast.BinOp) and type(node.op) in _BIN:
            sites.append((node, "op", _BIN[type(node.op)]()))
        elif isinstance(node, ast.Constant) and isinstance(node.value, bool):
            sites.append((node, "value", not node.value))
        elif isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docs:
            value = node.value
            for start, end, repl in _js_sites(value):
                sites.append((node, "value", value[:start] + repl + value[end:]))
    return sites


def _mutation(root, slug, tests):
    if not tests:
        return 1.0, None
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        gen = tmp / "gen"
        copy = gen / slug
        shutil.copytree(root / "gen" / slug, copy, ignore=shutil.ignore_patterns("__pycache__"))
        for other in sorted((root / "gen").iterdir()):
            if other.is_dir() and other.name != slug:
                (gen / other.name).symlink_to(other.resolve())
        test_dir = tmp / "tests"
        test_dir.mkdir()
        files = []
        for cid, content in tests:
            path = test_dir / _test_filename(cid)
            path.write_text(content, encoding="utf-8")
            files.append(path)
        rc, _, elapsed = _pytest(files, copy, copy, TIMEOUT, {}, ["--noconftest"])
        if rc is None:
            return None, f"mutation baseline timed out in the sandbox after {TIMEOUT} seconds"
        if rc != 0:
            return None, f"mutation baseline failed in the sandbox: pytest exited {rc}"
        limit = max(2.0, 10 * elapsed)
        killed = total = 0
        for py in sorted(copy.rglob("*.py")):
            original = py.read_text(encoding="utf-8")
            tree = ast.parse(original)
            for node, attr, new in _sites(tree):
                old = getattr(node, attr)
                setattr(node, attr, new)
                mutated = ast.unparse(tree)
                setattr(node, attr, old)
                py.write_text(mutated, encoding="utf-8")
                rc, _, _ = _pytest(files, copy, copy, limit, {}, ["--noconftest"])
                killed += rc != 0
                total += 1
            py.write_text(original, encoding="utf-8")
        return (killed / total if total else 1.0), None


# ---------------------------------------------------------------- verify


def _with_detail(base, detail, origin="implementation", extra=None):
    entry = dict(base)
    entry["result"] = "pass" if detail is None else "fail"
    entry.update(extra or {})
    if detail is not None:
        entry["failure_detail"] = detail
        entry["failure_origin"] = origin
    return entry


def verify(component_id, repo_root, judge=None, test_author=None):
    root = Path(repo_root).absolute()
    slug = component_id.removeprefix("comp-")
    comp_dir = root / "specs" / "components" / slug
    meta = _frontmatter(comp_dir / "component.md")
    sealed = meta.get("sealed") == "true"
    code_dir = root / meta["source_path"] if sealed else root / "gen" / slug
    specs = _read_criteria(comp_dir / "acceptance")

    loaded = {}

    def dep(name, rel):
        key = (str(root), name)
        if key not in loaded:
            loaded[key] = _load_dependency(root, rel, name)
        return loaded[key]

    def bundle_for(cid):
        assembler = dep("spec_bundle_assembler", "gen/spec-bundle-assembler")
        return assembler.assemble_criterion(component_id, cid, root)

    def generated(cid):
        cached = root / "verification" / slug / "generated-test" / _test_filename(cid)
        content = None
        authoring = None
        bundle = None
        if cached.is_file() or test_author is not None:
            bundle = bundle_for(cid)
            text = (_get(bundle, "criterion_text") + "\n" + _get(bundle, "requirement_text")).encode("utf-8")
            header = "# hotdocs-criterion: sha256:" + hashlib.sha256(text).hexdigest()
            if cached.is_file():
                cached_text = cached.read_text(encoding="utf-8")
                if cached_text.split("\n", 1)[0] == header:
                    content = cached_text
        if content is None and test_author is None:
            return _detail("no cached test and no test_author configured"), "test", None, None
        if content is None:
            result = test_author(bundle)
            if _get(_get(result, "model_call_error"), "category") in _RETRYABLE:
                result = test_author(bundle)
            error = _get(result, "model_call_error")
            authoring = {k: _get(result, k) for k in ("model", "seed", "prompt_version", "cache_hit")}
            if error is not None:
                message = f"test authoring failed: {_get(error, 'category')}: {_get(error, 'message')}"
                return _detail(message), "test", authoring, None
            content = _get(_get(result, "file"), "content")
        return _run_test(content, cid, root, code_dir), "implementation", authoring, content

    outputs = {}
    if not sealed and any(s["kind"] == "compiled" for s in specs):
        compiler = dep("criterion_compiler", "pipeline/criterion-compiler")
        report = compiler.compile(component_id, root)
        outputs = {_get(o, "criterion_id"): o for o in _get(report, "outputs")}
    cases = _characterize(root, slug, code_dir) if sealed else None

    criteria = []
    passing = []
    for spec in specs:
        cid, kind = spec["id"], spec["kind"]
        base = {"id": cid, "covers": spec["covers"], "kind": kind}
        if kind == "llm-judge":
            if judge is None:
                result, rationale = "skipped", None
            else:
                outcome = judge(bundle_for(cid))
                verdict = _get(outcome, "result")
                verdict = _get(outcome, "verdict") if verdict is None else verdict
                verdict = outcome if verdict is None else verdict
                result = "pass" if verdict is True or str(verdict).lower() == "pass" else "fail"
                rationale = _get(outcome, "rationale")
            criteria.append({**base, "result": result, "rationale": rationale})
        elif sealed:
            criteria.append(_with_detail(base, _sealed_detail(cases, cid)))
        elif kind == "compiled":
            out = outputs.get(cid)
            if _get(out, "status") == "compiled":
                content = (root / _get(out, "file")).read_text(encoding="utf-8")
                detail = _run_test(content, cid, root, code_dir)
            else:
                detail = _detail(_get(out, "message") or f"{cid} was not compiled")
            criteria.append(_with_detail(base, detail))
        else:
            detail, origin, authoring, content = generated(cid)
            extra = {"test_authoring": authoring} if authoring is not None else None
            criteria.append(_with_detail(base, detail, origin, extra))
            if detail is None:
                passing.append((cid, content))

    requirement_results = {}
    for path in sorted((comp_dir / "requirements").glob("R-*.md")):
        covering = [c for c in criteria if c["covers"] == path.stem]
        ok = bool(covering) and all(c["result"] == "pass" for c in covering)
        requirement_results[path.stem] = "pass" if ok else "fail"

    drift = _interface_drift(comp_dir, code_dir, slug)
    failed = any(c["result"] == "fail" for c in criteria) or drift

    if sealed:
        score, error = None, None
        failed = failed or not code_dir.is_dir()
    else:
        score, error = _mutation(root, slug, passing)
        threshold = 0.9 if any(s["kind"] == "generated-test" and s["freeform"] for s in specs) else 0.8
        failed = failed or error is not None or score < threshold

    return VerificationReport(
        component_id=component_id,
        criteria=criteria,
        requirement_results=requirement_results,
        interface_drift=drift,
        mutation_score=score,
        mutation_error=error,
        overall="fail" if failed else "pass",
    )


# ---------------------------------------------------------------- CLI


def _usage():
    print(_USAGE, file=sys.stderr)
    return 2


def main(argv):
    args = list(argv)
    opts = {"--repo-root": ".", "--format": "text"}
    component_id = None
    i = 0
    while i < len(args):
        arg = args[i]
        name, eq, value = arg.partition("=")
        if name in opts:
            if not eq:
                if i + 1 >= len(args):
                    return _usage()
                i += 1
                value = args[i]
            opts[name] = value
        elif component_id is None and not arg.startswith("-"):
            component_id = arg
        else:
            return _usage()
        i += 1
    if component_id is None or opts["--format"] not in ("json", "text"):
        return _usage()
    root = Path(opts["--repo-root"])
    if not (root / "specs" / "components" / component_id.removeprefix("comp-") / "component.md").is_file():
        return _usage()
    report = verify(component_id, root)
    if opts["--format"] == "json":
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print(f"{report.component_id}: {report.overall}")
        for c in report.criteria:
            print(f"  {c['id']}: {c['result']}")
    return 0 if report.overall == "pass" else 1
