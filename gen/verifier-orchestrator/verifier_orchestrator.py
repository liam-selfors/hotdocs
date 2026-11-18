"""Verifier orchestrator: runs every verification gate for one component."""

import ast
import dataclasses
import hashlib
import importlib.util
import inspect
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
from dataclasses import dataclass, field
from pathlib import Path

GATE_VERSION = "verifier-orchestrator@2.2.0"

TEST_TIMEOUT = 300
_RETRYABLE = ("network", "timeout", "rate_limit")
_USAGE = (
    "usage: hotdocs verify-component <component-id> "
    "[--repo-root=<dir>] [--format=json|text]"
)

_CMP_SWAP = {
    ast.Eq: ast.NotEq,
    ast.NotEq: ast.Eq,
    ast.Lt: ast.GtE,
    ast.GtE: ast.Lt,
    ast.Gt: ast.LtE,
    ast.LtE: ast.Gt,
    ast.Is: ast.IsNot,
    ast.IsNot: ast.Is,
    ast.In: ast.NotIn,
    ast.NotIn: ast.In,
}
_BIN_SWAP = {
    ast.Add: ast.Sub,
    ast.Sub: ast.Add,
    ast.Mult: ast.Div,
    ast.Div: ast.Mult,
    ast.FloorDiv: ast.Mod,
    ast.Mod: ast.FloorDiv,
}


@dataclass
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


@dataclass
class _Context:
    component_id: str
    repo_root: object
    root: Path
    slug: str
    code_dir: Path
    work: Path
    judge: object
    test_author: object
    assembler: list = field(default_factory=list)
    passing_tests: list = field(default_factory=list)

    def bundle_for(self, criterion_id):
        if not self.assembler:
            self.assembler.append(
                _load_dependency(self.root, "gen/spec-bundle-assembler", "spec_bundle_assembler")
            )
        return self.assembler[0].assemble_criterion(
            self.component_id, criterion_id, self.repo_root
        )


def _get(obj, key, default=None):
    if isinstance(obj, Mapping):
        return obj.get(key, default)
    return getattr(obj, key, default)


# ---------------------------------------------------------------- loading


def _tool_root():
    return next(p for p in Path(__file__).resolve().parents if p.name == "gen").parent


def _load_from_dir(base, module_name):
    path = base / f"{module_name}.py"
    if not path.is_file():
        path = base / module_name / "__init__.py"
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _load_dependency(root, rel, module_name):
    base = root / rel
    if not base.is_dir():
        base = _tool_root() / rel
    return _load_from_dir(base, module_name)


# ---------------------------------------------------------------- parsing


def _frontmatter(text):
    m = re.match(r"---\n(.*?)\n---", text, re.S)
    return m.group(1) if m else ""


def _parse_criterion(path):
    text = path.read_text(encoding="utf-8")
    cid = re.search(r"^#\s+(AC-\S+)\s*$", text, re.M).group(1)
    covers = re.search(r"Covers:\s*(\S+)", text)
    kind = re.search(r"^Kind:\s*(\S+)\s*$", text[covers.end():], re.M).group(1)
    return {
        "id": cid,
        "covers": covers.group(1).strip("`"),
        "kind": kind,
        "freeform": re.search(r"^\s*```gherkin\s*$", text, re.M) is None,
    }


def _test_filename(criterion_id):
    return "test_" + criterion_id.lower().replace("-", "_") + ".py"


def _plain_blocks(text):
    blocks, current, fence = [], None, None
    for line in text.split("\n"):
        stripped = line.strip()
        if fence is None:
            m = re.match(r"(`{3,})(.*)$", stripped)
            if m:
                fence = m.group(1)
                current = [] if m.group(2).strip() == "" else None
        elif stripped.startswith(fence) and stripped.strip("`") == "":
            if current is not None:
                blocks.append("\n".join(current))
            fence = None
        elif current is not None:
            current.append(line)
    return blocks


def _param_names(params):
    parts, depth, cur = [], 0, ""
    for ch in params:
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append(cur)
            cur = ""
        else:
            cur += ch
    parts.append(cur)
    names = []
    for part in parts:
        name = re.split(r"[:=]", part, maxsplit=1)[0].strip().lstrip("*").strip()
        if name and name != "/":
            names.append(name)
    return names


def _documented_callables(text):
    found = []
    for block in _plain_blocks(text):
        for m in re.finditer(r"^[ \t]*([A-Za-z_][\w.]*)\(", block, re.M):
            depth, j = 1, m.end()
            while depth and j < len(block):
                depth += {"(": 1, ")": -1}.get(block[j], 0)
                j += 1
            found.append((m.group(1), _param_names(block[m.end():j - 1])))
    return found


# ---------------------------------------------------------------- drift


def _mismatch(module, name, params):
    obj = module
    for part in name.split("."):
        obj = getattr(obj, part, None)
    if not callable(obj):
        return True
    actual = [p.name for p in inspect.signature(obj).parameters.values()]
    return actual != params


def _interface_drift(spec_dir, code_dir, module_name):
    documented = []
    for name in ("library.md", "cli.md"):
        path = spec_dir / "interface" / name
        if path.is_file():
            documented += _documented_callables(path.read_text(encoding="utf-8"))
    if not documented:
        return False
    try:
        module = _load_from_dir(code_dir, module_name)
    except Exception:
        module = None
    return any(_mismatch(module, name, params) for name, params in documented)


# ---------------------------------------------------------------- running


def _run(cmd, cwd, pythonpath, timeout):
    env = dict(os.environ, PYTHONPATH=str(pythonpath), PYTHONDONTWRITEBYTECODE="1")
    start = time.monotonic()
    proc = subprocess.Popen(
        cmd,
        cwd=str(cwd),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    try:
        out, _ = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL)
        out, _ = proc.communicate()
        return None, out.decode("utf-8", "replace"), time.monotonic() - start
    return proc.returncode, out.decode("utf-8", "replace"), time.monotonic() - start


def _detail(message, expected=None, actual=None):
    return {"message": message, "expected": expected, "actual": actual}


def _timeout_detail():
    return _detail(f"timed out after {TEST_TIMEOUT} seconds")


def _compared(expr):
    for op in (" == ", " in "):
        pieces = expr.split(op)
        for k in range(1, len(pieces)):
            try:
                left = ast.literal_eval(op.join(pieces[:k]))
                right = ast.literal_eval(op.join(pieces[k:]))
            except Exception:
                continue
            return (right, left) if op == " == " else (left, right)
    return None, None


def _detail_from_output(text):
    e_lines = [line[1:].strip() for line in text.splitlines() if line.startswith("E ")]
    e_lines = [line for line in e_lines if line]
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    message = e_lines[0] if e_lines else (lines[-1] if lines else "")
    message = message.removeprefix("AssertionError: ")
    expected = actual = None
    for line in e_lines:
        if line.startswith("assert "):
            expected, actual = _compared(line[len("assert "):])
            break
    return _detail(message, expected, actual)


def _fail(entry, detail, origin):
    entry["result"] = "fail"
    entry["failure_detail"] = detail
    entry["failure_origin"] = origin
    return entry


def _run_criterion(entry, test_file, ctx):
    code, out, _ = _run(
        [sys.executable, "-m", "pytest", str(test_file)], ctx.root, ctx.code_dir, TEST_TIMEOUT
    )
    if code == 0:
        entry["result"] = "pass"
        return True
    _fail(entry, _timeout_detail() if code is None else _detail_from_output(out), "implementation")
    return False


# ---------------------------------------------------------------- kinds


def _base(spec):
    return {"id": spec["id"], "covers": spec["covers"], "kind": spec["kind"]}


def _judge_outcome(outcome):
    if isinstance(outcome, (bool, str)):
        return ("pass" if outcome in (True, "pass") else "fail"), None
    value = _get(outcome, "result")
    if value is None:
        value = _get(outcome, "verdict")
    return ("pass" if value in (True, "pass") else "fail"), _get(outcome, "rationale")


def _judge_entry(spec, ctx):
    entry = _base(spec)
    if ctx.judge is None:
        entry["result"] = "skipped"
        entry["rationale"] = None
        return entry
    result, rationale = _judge_outcome(ctx.judge(ctx.bundle_for(spec["id"])))
    entry["result"] = result
    entry["rationale"] = rationale
    return entry


def _is_fresh(path, digest):
    return path.is_file() and (
        path.read_text(encoding="utf-8").split("\n", 1)[0]
        == f"# hotdocs-criterion: sha256:{digest}"
    )


def _generated_entry(spec, ctx):
    entry = _base(spec)
    bundle = ctx.bundle_for(spec["id"])
    digest = hashlib.sha256(
        (_get(bundle, "criterion_text") + "\n" + _get(bundle, "requirement_text")).encode("utf-8")
    ).hexdigest()
    name = _test_filename(spec["id"])
    cached = ctx.root / "verification" / ctx.slug / "generated-test" / name
    if _is_fresh(cached, digest):
        path = cached
    elif ctx.test_author is None:
        return _fail(entry, _detail("no cached test and no test_author configured"), "test")
    else:
        outcome = ctx.test_author(bundle)
        error = _get(outcome, "model_call_error")
        if error and _get(error, "category") in _RETRYABLE:
            outcome = ctx.test_author(bundle)
            error = _get(outcome, "model_call_error")
        entry["test_authoring"] = {
            "model": _get(outcome, "model"),
            "seed": _get(outcome, "seed"),
            "prompt_version": _get(outcome, "prompt_version"),
            "cache_hit": _get(outcome, "cache_hit"),
        }
        if error:
            message = (
                f"test authoring failed: {_get(error, 'category')}: {_get(error, 'message')}"
            )
            return _fail(entry, _detail(message), "test")
        path = ctx.work / "authored" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_get(_get(outcome, "file"), "content"), encoding="utf-8")
    if _run_criterion(entry, path, ctx):
        ctx.passing_tests.append(path)
    return entry


def _compiled_entry(spec, outputs, ctx):
    entry = _base(spec)
    output = outputs.get(spec["id"])
    if _get(output, "status") == "compiled":
        _run_criterion(entry, ctx.root / _get(output, "file"), ctx)
        return entry
    return _fail(
        entry, _detail(_get(output, "message", "criterion was not compiled")), "implementation"
    )


# ---------------------------------------------------------------- mutation


def _sites(tree):
    return [
        node
        for node in ast.walk(tree)
        if (isinstance(node, ast.Compare) and len(node.ops) == 1)
        or isinstance(node, ast.BoolOp)
        or (isinstance(node, ast.BinOp) and type(node.op) in _BIN_SWAP)
        or (isinstance(node, ast.Constant) and type(node.value) is bool)
    ]


def _mutate(node):
    if isinstance(node, ast.Compare):
        node.ops = [_CMP_SWAP[type(node.ops[0])]()]
    elif isinstance(node, ast.BoolOp):
        node.op = ast.Or() if isinstance(node.op, ast.And) else ast.And()
    elif isinstance(node, ast.BinOp):
        node.op = _BIN_SWAP[type(node.op)]()
    else:
        node.value = not node.value


def _mutation(ctx):
    if not ctx.passing_tests:
        return 1.0, None
    copy = ctx.work / "sandbox" / "gen" / ctx.slug
    shutil.copytree(
        ctx.root / "gen" / ctx.slug, copy, ignore=shutil.ignore_patterns("__pycache__")
    )
    for other in sorted((ctx.root / "gen").iterdir()):
        if other.is_dir() and other.name != ctx.slug:
            os.symlink(other, copy.parent / other.name)
    cmd = [sys.executable, "-m", "pytest", "--noconftest", *map(str, ctx.passing_tests)]
    code, _, elapsed = _run(cmd, copy, copy, TEST_TIMEOUT)
    if code is None:
        return None, f"mutation baseline timed out in the sandbox after {TEST_TIMEOUT} seconds"
    if code != 0:
        return None, f"mutation baseline failed in the sandbox: pytest exited {code}"
    timeout = max(2.0, 10 * elapsed)
    killed = total = 0
    for path in sorted(copy.rglob("*.py")):
        source = path.read_text(encoding="utf-8")
        for index in range(len(_sites(ast.parse(source)))):
            tree = ast.parse(source)
            _mutate(_sites(tree)[index])
            path.write_text(ast.unparse(tree), encoding="utf-8")
            code, _, _ = _run(cmd, copy, copy, timeout)
            killed += code != 0
            total += 1
        path.write_text(source, encoding="utf-8")
    return (killed / total if total else 1.0), None


# ---------------------------------------------------------------- sealed


def _junit_records(junit):
    records = {}
    if not junit.is_file():
        return records
    for case in ET.parse(junit).getroot().iter("testcase"):
        name = case.get("name", "").split("[", 1)[0]
        bad = [c for c in case if c.tag in ("failure", "error", "skipped")]
        text = (
            bad[0].get("message", "") + "\n" + "".join(bad[0].itertext()) if bad else None
        )
        records.setdefault(name, []).append(text)
    return records


def _sealed_criteria(specs, ctx):
    files = sorted((ctx.root / "verification" / ctx.slug).glob("test_*.py"))
    records, timed_out = {}, False
    if files:
        junit = ctx.work / "characterization.xml"
        code, _, _ = _run(
            [sys.executable, "-m", "pytest", *map(str, files), f"--junitxml={junit}"],
            ctx.root,
            ctx.code_dir,
            TEST_TIMEOUT,
        )
        timed_out = code is None
        records = _junit_records(junit)
    criteria = []
    for spec in specs:
        if spec["kind"] == "llm-judge":
            criteria.append(_judge_entry(spec, ctx))
            continue
        entry = _base(spec)
        base = "test_" + spec["id"].lower().replace("-", "_")
        matched = [
            r for n, rs in records.items() if n == base or n.startswith(base + "_") for r in rs
        ]
        failures = [r for r in matched if r is not None]
        if timed_out:
            _fail(entry, _timeout_detail(), "implementation")
        elif not matched:
            _fail(entry, _detail("no characterization test"), "implementation")
        elif failures:
            _fail(entry, _detail_from_output(failures[0]), "implementation")
        else:
            entry["result"] = "pass"
        criteria.append(entry)
    return criteria


# ---------------------------------------------------------------- verify


def verify(component_id, repo_root, judge=None, test_author=None):
    root = Path(repo_root).resolve()
    slug = component_id.removeprefix("comp-")
    module_name = slug.replace("-", "_")
    spec_dir = root / "specs" / "components" / slug
    fm = _frontmatter((spec_dir / "component.md").read_text(encoding="utf-8"))
    source = re.search(r"^source_path:\s*(\S.*?)\s*$", fm, re.M)
    sealed = re.search(r"^sealed:\s*true\s*$", fm, re.M) is not None and source is not None
    code_dir = root / source.group(1) if sealed else root / "gen" / slug
    specs = [_parse_criterion(p) for p in sorted((spec_dir / "acceptance").glob("AC-*.md"))]

    with tempfile.TemporaryDirectory() as work_name:
        ctx = _Context(
            component_id=component_id,
            repo_root=repo_root,
            root=root,
            slug=slug,
            code_dir=code_dir,
            work=Path(work_name),
            judge=judge,
            test_author=test_author,
        )
        if sealed:
            criteria = _sealed_criteria(specs, ctx)
            mutation_score, mutation_error = None, None
            bad_mutation = not code_dir.is_dir()
        else:
            outputs = {}
            if any(s["kind"] == "compiled" for s in specs):
                compiler = _load_dependency(root, "pipeline/criterion-compiler", "criterion_compiler")
                report = compiler.compile(component_id, repo_root, "pytest", ctx.work / "compiled")
                outputs = {_get(o, "criterion_id"): o for o in _get(report, "outputs", [])}
            criteria = []
            for spec in specs:
                if spec["kind"] == "compiled":
                    criteria.append(_compiled_entry(spec, outputs, ctx))
                elif spec["kind"] == "generated-test":
                    criteria.append(_generated_entry(spec, ctx))
                else:
                    criteria.append(_judge_entry(spec, ctx))
            mutation_score, mutation_error = _mutation(ctx)
            freeform = any(s["freeform"] for s in specs if s["kind"] == "generated-test")
            threshold = 0.9 if freeform else 0.8
            bad_mutation = mutation_error is not None or mutation_score < threshold
        drift = _interface_drift(spec_dir, code_dir, module_name)

    requirement_results = {
        p.stem: (
            "pass"
            if all(c["result"] == "pass" for c in criteria if c["covers"] == p.stem)
            else "fail"
        )
        for p in sorted((spec_dir / "requirements").glob("R-*.md"))
    }
    failed = any(c["result"] == "fail" for c in criteria)
    overall = "fail" if failed or drift or bad_mutation else "pass"
    return VerificationReport(
        component_id=component_id,
        criteria=criteria,
        requirement_results=requirement_results,
        interface_drift=drift,
        mutation_score=mutation_score,
        mutation_error=mutation_error,
        overall=overall,
    )


# ---------------------------------------------------------------- CLI


def _usage():
    print(_USAGE, file=sys.stderr)
    return 2


def main(argv):
    args = list(argv)
    options = {"--repo-root": ".", "--format": "text"}
    component_id = None
    i = 0
    while i < len(args):
        arg = args[i]
        name, sep, value = arg.partition("=")
        if name in options and sep:
            options[name] = value
        elif arg in options and i + 1 < len(args):
            options[arg] = args[i + 1]
            i += 1
        elif component_id is None and not arg.startswith("-"):
            component_id = arg
        else:
            return _usage()
        i += 1
    if component_id is None or options["--format"] not in ("json", "text"):
        return _usage()
    repo_root = Path(options["--repo-root"])
    slug = component_id.removeprefix("comp-")
    if not (repo_root / "specs" / "components" / slug / "component.md").is_file():
        return _usage()
    report = verify(component_id, repo_root)
    if options["--format"] == "json":
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print(f"{report.component_id}: {report.overall}")
        for c in report.criteria:
            print(f"  {c['id']}: {c['result']}")
    return 0 if report.overall == "pass" else 1
