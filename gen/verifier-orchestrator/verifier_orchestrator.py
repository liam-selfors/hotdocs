"""Verifier orchestrator: runs every verification gate for one component."""

from __future__ import annotations

import ast
import dataclasses
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
from pathlib import Path

GATE_VERSION = "verifier-orchestrator@2.0.0"

MUTATION_BAR = 0.9
UNMUTATED_TIMEOUT = 300
USAGE = (
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


@dataclasses.dataclass
class VerificationReport:
    component_id: str
    criteria: list
    requirement_results: dict
    interface_drift: bool
    mutation_score: float | None
    overall: str

    def to_dict(self):
        return dataclasses.asdict(self)


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


# --- module loading -------------------------------------------------------


def _tool_root():
    here = Path(__file__).resolve()
    return next(p for p in here.parents if p.name == "gen").parent


def _load_module(base, name):
    flat = base / f"{name}.py"
    if flat.is_file():
        spec = importlib.util.spec_from_file_location(name, flat)
    else:
        pkg = base / name
        spec = importlib.util.spec_from_file_location(
            name, pkg / "__init__.py", submodule_search_locations=[str(pkg)]
        )
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _load_dependency(loaded, repo_root, rel_dir, name):
    key = (str(repo_root), name)
    if key not in loaded:
        base = Path(repo_root) / rel_dir
        if not base.is_dir():
            base = _tool_root() / rel_dir
        loaded[key] = _load_module(base, name)
    return loaded[key]


def _load_candidate(code_dir, name):
    try:
        return _load_module(code_dir, name)
    except Exception:
        return None


# --- spec reading ---------------------------------------------------------


def _frontmatter(path):
    text = path.read_text() if path.is_file() else ""
    m = re.match(r"---\n(.*?)\n---", text, re.S)
    body = m.group(1) if m else ""
    fields = {}
    for line in body.splitlines():
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip()
    return fields


def _criteria(acc_dir):
    out = []
    for path in sorted(acc_dir.glob("AC-*.md")):
        text = path.read_text()
        cid = re.search(r"^#\s+(AC-\S+)", text, re.M).group(1)
        covers = re.search(r"Covers:\s*([RP]-[A-Za-z0-9-]+)", text).group(1)
        kind = re.search(r"^Kind:\s*(\S+)", text, re.M).group(1)
        out.append((cid, covers, kind))
    return out


def _test_base(criterion_id):
    return "test_" + criterion_id.lower().replace("-", "_")


# --- interface drift ------------------------------------------------------


def _plain_blocks(text):
    blocks, current, fence = [], None, None
    for line in text.splitlines():
        m = re.match(r"\s*(`{3,})\s*(\S*)", line)
        if fence is None:
            if m:
                fence = m.group(1)
                current = [] if m.group(2) == "" else None
        elif m and m.group(1) == fence and m.group(2) == "":
            if current is not None:
                blocks.append(current)
            fence = None
        elif current is not None:
            current.append(line)
    return blocks


def _parse_signature(text):
    name, _, rest = text.partition("(")
    depth, params, part = 1, [], ""
    for ch in rest:
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        if depth == 0:
            break
        if ch == "," and depth == 1:
            params.append(part)
            part = ""
        else:
            part += ch
    params.append(part)
    names = [p.split(":")[0].split("=")[0].strip().lstrip("*") for p in params]
    return name.strip(), [n for n in names if n not in ("", "/")]


def _signatures(lines):
    sigs, buf = [], ""
    for line in lines:
        if buf or re.match(r"\w+\(", line):
            buf = f"{buf} {line.strip()}" if buf else line.strip()
            if buf.count("(") == buf.count(")"):
                sigs.append(_parse_signature(buf))
                buf = ""
    return sigs


def _documented_callables(interface_dir):
    found = []
    for filename in ("library.md", "cli.md"):
        path = interface_dir / filename
        if path.is_file():
            for block in _plain_blocks(path.read_text()):
                found.extend(_signatures(block))
    return found


def _drift(module, documented):
    for name, params in documented:
        obj = getattr(module, name, None)
        try:
            actual = list(inspect.signature(obj).parameters)
        except (TypeError, ValueError):
            return True
        if actual != params:
            return True
    return False


# --- test execution -------------------------------------------------------


def _pytest(targets, cwd, pythonpath, timeout, *extra):
    env = dict(os.environ, PYTHONPATH=str(pythonpath))
    cmd = [
        sys.executable, "-m", "pytest", "-vv", "-p", "no:cacheprovider",
        *extra, *[str(t) for t in targets],
    ]
    start = time.monotonic()
    proc = subprocess.Popen(
        cmd, cwd=str(cwd), env=env, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, text=True, start_new_session=True,
    )
    try:
        output, _ = proc.communicate(timeout=timeout)
        code = proc.returncode
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL)
        output, _ = proc.communicate()
        code = None
    return code, output, time.monotonic() - start


def _literal(node):
    try:
        return ast.literal_eval(node)
    except Exception:
        return None


def _compared(expr):
    try:
        node = ast.parse(expr, mode="eval").body
    except SyntaxError:
        return None, None
    if not (isinstance(node, ast.Compare) and len(node.ops) == 1):
        return None, None
    left, right = node.left, node.comparators[0]
    if isinstance(node.ops[0], (ast.In, ast.NotIn)):
        return _literal(left), _literal(right)
    return _literal(right), _literal(left)


def _failure_detail(output):
    errors = [line[1:].strip() for line in output.splitlines() if line.startswith("E ")]
    for text in errors:
        m = re.match(r"(?:AssertionError: )?assert (.+)$", text)
        if m:
            expected, actual = _compared(m.group(1))
            return {"message": text, "expected": expected, "actual": actual}
    lines = errors or [line for line in output.splitlines() if line.strip()]
    return {"message": lines[-1].strip(), "expected": None, "actual": None}


def _fail(entry, message):
    entry["result"] = "fail"
    entry["failure_detail"] = {"message": message, "expected": None, "actual": None}


def _record(entry, code, output):
    if code == 0:
        entry["result"] = "pass"
    elif code is None:
        _fail(entry, f"timed out after {UNMUTATED_TIMEOUT} seconds")
    else:
        entry["result"] = "fail"
        entry["failure_detail"] = _failure_detail(output)


def _char_tests(ver_dir):
    return [
        (path, node.name)
        for path in sorted(ver_dir.glob("test_*.py"))
        for node in ast.parse(path.read_text()).body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]


# --- llm-judge ------------------------------------------------------------


def _judge(judge, bundle_for, criterion_id):
    if judge is None:
        return "skipped", None
    bundle = bundle_for(criterion_id)
    try:
        outcome = judge(bundle)
    except Exception as exc:
        return "skipped", str(exc)
    if outcome is None or isinstance(outcome, (bool, str)):
        value, rationale = outcome, None
    else:
        value = _get(outcome, "result")
        if value is None:
            value = _get(outcome, "verdict")
        rationale = _get(outcome, "rationale")
    if value is True or value == "pass":
        return "pass", rationale
    if value is False or value == "fail":
        return "fail", rationale
    return "skipped", rationale


# --- mutation testing -----------------------------------------------------


def _sites(tree):
    sites = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare) and len(node.ops) == 1:
            sites.append(node)
        elif isinstance(node, ast.BoolOp):
            sites.append(node)
        elif isinstance(node, ast.BinOp) and type(node.op) in _BIN_SWAP:
            sites.append(node)
        elif isinstance(node, ast.Constant) and isinstance(node.value, bool):
            sites.append(node)
    return sites


def _mutant(source, index):
    tree = ast.parse(source)
    node = _sites(tree)[index]
    if isinstance(node, ast.Compare):
        node.ops = [_CMP_SWAP[type(node.ops[0])]()]
    elif isinstance(node, ast.BoolOp):
        node.op = ast.Or() if isinstance(node.op, ast.And) else ast.And()
    elif isinstance(node, ast.BinOp):
        node.op = _BIN_SWAP[type(node.op)]()
    else:
        node.value = not node.value
    return ast.unparse(tree)


def _mutation_score(code_dir, test_files, baseline):
    timeout = max(2.0, 10 * baseline)
    killed = total = 0
    for source in sorted(code_dir.rglob("*.py")):
        text = source.read_text()
        for index in range(len(_sites(ast.parse(text)))):
            total += 1
            with tempfile.TemporaryDirectory() as tmp:
                copy = Path(tmp) / code_dir.name
                shutil.copytree(
                    code_dir, copy, ignore=shutil.ignore_patterns("__pycache__")
                )
                (copy / source.relative_to(code_dir)).write_text(_mutant(text, index))
                code, _, _ = _pytest(test_files, copy, copy, timeout, "--noconftest")
            killed += code != 0
    return killed / total if total else 1.0


# --- orchestration --------------------------------------------------------


def verify(component_id: str, repo_root: Path, judge=None, test_author=None) -> VerificationReport:
    root = Path(repo_root).resolve()
    slug = component_id.removeprefix("comp-")
    module_name = slug.replace("-", "_")
    spec_dir = root / "specs" / "components" / slug
    ver_dir = root / "verification" / slug
    fm = _frontmatter(spec_dir / "component.md")
    sealed = fm.get("sealed") == "true"
    code_dir = root / fm["source_path"] if sealed else root / "gen" / slug
    loaded = {}

    def bundle_for(criterion_id):
        sba = _load_dependency(
            loaded, repo_root, "gen/spec-bundle-assembler", "spec_bundle_assembler"
        )
        return sba.assemble_criterion(component_id, criterion_id, repo_root)

    parsed = _criteria(spec_dir / "acceptance")

    compiled = {}
    if not sealed and any(kind == "compiled" for _, _, kind in parsed):
        cc = _load_dependency(
            loaded, repo_root, "pipeline/criterion-compiler", "criterion_compiler"
        )
        report = cc.compile(component_id, repo_root)
        compiled = {_get(o, "criterion_id"): o for o in _get(report, "outputs")}

    char_tests = _char_tests(ver_dir) if sealed else []

    criteria, passing_files, baseline = [], [], 0.0
    for cid, covers, kind in parsed:
        entry = {"id": cid, "covers": covers, "kind": kind}
        if kind == "llm-judge":
            entry["result"], entry["rationale"] = _judge(judge, bundle_for, cid)
        elif sealed:
            base = _test_base(cid)
            targets = [
                f"{path}::{name}"
                for path, name in char_tests
                if name == base or name.startswith(base + "_")
            ]
            if targets:
                code, output, _ = _pytest(targets, root, code_dir, UNMUTATED_TIMEOUT)
                _record(entry, code, output)
            else:
                _fail(entry, "no characterization test")
        elif kind == "compiled":
            out = compiled.get(cid)
            if _get(out, "status") == "compiled":
                test_file = root / _get(out, "file")
                code, output, _ = _pytest([test_file], root, code_dir, UNMUTATED_TIMEOUT)
                _record(entry, code, output)
            else:
                _fail(entry, str(_get(out, "message", "criterion-compiler produced no output")))
        else:
            test_file = ver_dir / "generated-test" / (_test_base(cid) + ".py")
            authoring = None
            if not test_file.is_file() and test_author is not None:
                outcome = test_author(bundle_for(cid))
                authoring = {
                    key: _get(outcome, key)
                    for key in ("model", "seed", "prompt_version", "cache_hit")
                }
                error = _get(outcome, "model_call_error")
                if error is None:
                    test_file.parent.mkdir(parents=True, exist_ok=True)
                    test_file.write_text(_get(_get(outcome, "file"), "content"))
            if test_file.is_file():
                code, output, duration = _pytest(
                    [test_file], root, code_dir, UNMUTATED_TIMEOUT
                )
                _record(entry, code, output)
                if code == 0:
                    passing_files.append(test_file)
                    baseline += duration
            elif authoring is None:
                _fail(entry, "no cached test and no test_author configured")
            else:
                _fail(entry, f"test_author model_call_error: {error}")
            if authoring is not None:
                entry["test_authoring"] = authoring
        criteria.append(entry)

    module = _load_candidate(code_dir, module_name)
    drift = _drift(module, _documented_callables(spec_dir / "interface"))

    mutation_score = None
    if not sealed and any(kind == "generated-test" for _, _, kind in parsed):
        mutation_score = (
            _mutation_score(code_dir, passing_files, baseline) if passing_files else 0.0
        )

    covering = {}
    for c in criteria:
        covering.setdefault(c["covers"], []).append(c["result"])
    declared = {p.stem for p in (spec_dir / "requirements").glob("R-*.md")}
    requirement_results = {
        rid: "pass"
        if covering.get(rid) and all(r == "pass" for r in covering[rid])
        else "fail"
        for rid in sorted(declared | covering.keys())
    }

    failed = any(c["result"] == "fail" for c in criteria)
    below_bar = mutation_score is not None and mutation_score < MUTATION_BAR
    missing_source = sealed and not code_dir.is_dir()
    overall = "fail" if failed or drift or below_bar or missing_source else "pass"

    return VerificationReport(
        component_id=component_id,
        criteria=criteria,
        requirement_results=requirement_results,
        interface_drift=drift,
        mutation_score=mutation_score,
        overall=overall,
    )


# --- CLI ------------------------------------------------------------------


def _usage():
    print(USAGE, file=sys.stderr)
    return 2


def main(argv):
    args = list(argv)
    opts = {"--repo-root": ".", "--format": "text"}
    positional = []
    i = 0
    while i < len(args):
        name, eq, value = args[i].partition("=")
        if name in opts:
            if not eq:
                i += 1
                if i == len(args):
                    return _usage()
                value = args[i]
            opts[name] = value
        elif positional or args[i].startswith("-"):
            return _usage()
        else:
            positional.append(args[i])
        i += 1
    if not positional or opts["--format"] not in ("json", "text"):
        return _usage()
    component_id = positional[0]
    repo_root = Path(opts["--repo-root"])
    slug = component_id.removeprefix("comp-")
    if not (repo_root / "specs" / "components" / slug / "component.md").is_file():
        return _usage()
    report = verify(component_id, repo_root)
    if opts["--format"] == "json":
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print(f"{report.component_id}: {report.overall}")
        for c in report.criteria:
            print(f"  {c['id']}: {c['result']}")
    return 0 if report.overall == "pass" else 1
