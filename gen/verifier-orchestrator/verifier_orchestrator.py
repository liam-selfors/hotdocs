"""Verifier orchestrator: runs every applicable verification gate against one
component's code and produces a single structured VerificationReport."""
from __future__ import annotations

import ast
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
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

GATE_VERSION = "verifier-orchestrator@2.0.0"

_UNMUTATED_TIMEOUT = 300
_USAGE = (
    "usage: hotdocs verify-component <component-id> "
    "[--repo-root=<dir>] [--format=json|text]"
)

_SWAPS = {
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
    ast.And: ast.Or,
    ast.Or: ast.And,
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
    overall: str

    def to_dict(self):
        return {
            "component_id": self.component_id,
            "criteria": [dict(c) for c in self.criteria],
            "requirement_results": dict(self.requirement_results),
            "interface_drift": self.interface_drift,
            "mutation_score": self.mutation_score,
            "overall": self.overall,
        }


def _get(obj, key, default=None):
    if isinstance(obj, Mapping):
        return obj.get(key, default)
    return getattr(obj, key, default)


# ---------------------------------------------------------------- loading


def _tool_root():
    return next(p for p in Path(__file__).resolve().parents if p.name == "gen").parent


def _load_module(base_dir, module_name):
    path = base_dir / f"{module_name}.py"
    locations = None
    if not path.is_file():
        path = base_dir / module_name / "__init__.py"
        locations = [str(path.parent)]
    spec = importlib.util.spec_from_file_location(
        module_name, path, submodule_search_locations=locations
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _load_dependency(repo_root, rel, module_name):
    base = repo_root / rel
    if not base.is_dir():
        base = _tool_root() / rel
    return _load_module(base, module_name)


# ---------------------------------------------------------------- parsing


def _parse_criteria(acceptance_dir):
    parsed = []
    for path in sorted(acceptance_dir.glob("AC-*.md")):
        text = path.read_text(encoding="utf-8")
        covers = re.search(r"Covers: *(\S+)", text)
        parsed.append(
            {
                "id": re.search(r"^# +(AC-\S+)", text, re.M).group(1),
                "covers": covers.group(1),
                "kind": re.search(r"^Kind: *(\S+)", text[covers.end():], re.M).group(1),
                "freeform": re.search(r"^```gherkin\s*$", text, re.M) is None,
            }
        )
    return parsed


def _param_names(rest):
    pieces, depth, piece = [], 0, ""
    for ch in rest:
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            if depth == 0:
                break
            depth -= 1
        elif ch == "," and depth == 0:
            pieces.append(piece)
            piece = ""
            continue
        piece += ch
    pieces.append(piece)
    matches = (re.match(r"\s*\**([A-Za-z_]\w*)", p) for p in pieces)
    return [m.group(1) for m in matches if m]


def _documented_callables(text):
    found, buf, plain = [], None, None
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("```"):
            plain = (s == "```") if plain is None else None
            continue
        if not plain:
            continue
        if buf is None:
            if not re.match(r"[A-Za-z_]\w*\(", s):
                continue
            buf = s
        else:
            buf += " " + s
        if buf.count("(") > buf.count(")"):
            continue
        name, rest = buf.split("(", 1)
        found.append((name, _param_names(rest)))
        buf = None
    return found


def _interface_drift(spec_dir, code_dir, module_name):
    documented = []
    for name in ("library.md", "cli.md"):
        path = spec_dir / "interface" / name
        if path.is_file():
            documented += _documented_callables(path.read_text(encoding="utf-8"))
    try:
        module = _load_module(code_dir, module_name)
    except Exception:
        return True
    for name, params in documented:
        obj = getattr(module, name, None)
        if not callable(obj) or list(inspect.signature(obj).parameters) != params:
            return True
    return False


# ---------------------------------------------------------------- running


def _pytest(args, pythonpath, cwd, timeout, extra):
    env = dict(os.environ, PYTHONPATH=str(pythonpath), PYTHONDONTWRITEBYTECODE="1")
    command = [sys.executable, "-m", "pytest", "-vv", "-p", "no:cacheprovider", "-rfE"]
    start = time.monotonic()
    proc = subprocess.Popen(
        command + extra + [str(a) for a in args],
        cwd=str(cwd),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        start_new_session=True,
    )
    try:
        output, _ = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL)
        proc.communicate()
        return None, "", time.monotonic() - start
    return proc.returncode, output, time.monotonic() - start


def _compared(expr):
    try:
        node = ast.parse(expr, mode="eval").body
        if isinstance(node, ast.Compare) and len(node.ops) == 1 and isinstance(
            node.ops[0], (ast.Eq, ast.In)
        ):
            left = ast.literal_eval(node.left)
            right = ast.literal_eval(node.comparators[0])
            if isinstance(node.ops[0], ast.In):
                return left, right
            return right, left
    except Exception:
        pass
    return None, None


def _failure_detail(output):
    lines = output.splitlines()
    summary = [l for l in lines if l.startswith(("FAILED ", "ERROR "))]
    if summary:
        message = summary[0].split(" - ", 1)[-1]
    else:
        message = next((l.strip() for l in reversed(lines) if l.strip()), "")
    message = message.removeprefix("AssertionError: ")
    expected = actual = None
    for line in lines:
        m = re.match(r"E\s+(?:AssertionError: )?assert (.+)$", line)
        if m:
            expected, actual = _compared(m.group(1))
            break
    return {"message": message, "expected": expected, "actual": actual}


def _fail(message):
    return {
        "result": "fail",
        "failure_detail": {"message": message, "expected": None, "actual": None},
    }


def _run_check(args, code_dir, cwd):
    code, output, _ = _pytest(args, code_dir, cwd, _UNMUTATED_TIMEOUT, [])
    if code == 0:
        return {"result": "pass"}
    if code is None:
        return _fail(f"timed out after {_UNMUTATED_TIMEOUT} seconds")
    return {"result": "fail", "failure_detail": _failure_detail(output)}


# ---------------------------------------------------------------- dispatch


def _judge(judge, bundle_for, criterion_id):
    if judge is None:
        return {"result": "skipped", "rationale": None}
    bundle = bundle_for(criterion_id)
    try:
        outcome = judge(bundle)
    except Exception as exc:
        return {"result": "skipped", "rationale": str(exc)}
    if isinstance(outcome, Mapping) or hasattr(outcome, "result") or hasattr(outcome, "verdict"):
        value = _get(outcome, "result", _get(outcome, "verdict"))
        rationale = _get(outcome, "rationale")
    else:
        value, rationale = outcome, None
    if value is True or value == "pass":
        result = "pass"
    elif value is None or value == "skipped":
        result = "skipped"
    else:
        result = "fail"
    return {"result": result, "rationale": rationale}


def _generated_test(criterion_id, cached, author_dir, test_author, bundle_for):
    if cached.is_file():
        return cached, None, None
    if test_author is None:
        return None, None, "no cached test and no test_author configured"
    outcome = test_author(bundle_for(criterion_id))
    authoring = {
        key: _get(outcome, key) for key in ("model", "seed", "prompt_version", "cache_hit")
    }
    error = _get(outcome, "model_call_error")
    if error:
        return None, authoring, f"test_author model call error: {error}"
    path = author_dir / cached.name
    path.write_text(_get(_get(outcome, "file"), "content"), encoding="utf-8")
    return path, authoring, None


def _characterization_tests(verification_dir):
    tests = []
    for path in sorted(verification_dir.glob("test_*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        tests += [(path, n.name) for n in tree.body if isinstance(n, ast.FunctionDef)]
    return tests


def _characterize(tests, criterion_id, code_dir, cwd):
    prefix = "test_" + criterion_id.lower().replace("-", "_")
    node_ids = [
        f"{path}::{name}"
        for path, name in tests
        if name == prefix or name.startswith(prefix + "_")
    ]
    if not node_ids:
        return _fail("no characterization test")
    return _run_check(node_ids, code_dir, cwd)


# ---------------------------------------------------------------- mutation


def _sites(tree):
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Compare) and len(node.ops) == 1
        or isinstance(node, (ast.BoolOp, ast.BinOp)) and type(node.op) in _SWAPS
        or isinstance(node, ast.Constant) and isinstance(node.value, bool)
    ]


def _mutate(node):
    if isinstance(node, ast.Compare):
        node.ops = [_SWAPS[type(node.ops[0])]()]
    elif isinstance(node, ast.Constant):
        node.value = not node.value
    else:
        node.op = _SWAPS[type(node.op)]()


def _mutants(source):
    for index in range(len(_sites(ast.parse(source)))):
        tree = ast.parse(source)
        _mutate(_sites(tree)[index])
        yield ast.unparse(tree)


def _mutation_score(code_dir, tests):
    with tempfile.TemporaryDirectory() as tmp:
        copy = Path(tmp) / code_dir.name
        shutil.copytree(code_dir, copy, ignore=shutil.ignore_patterns("__pycache__"))
        mutants = []
        for path in sorted(copy.rglob("*.py")):
            source = path.read_text(encoding="utf-8")
            mutants += [(path, source, mutant) for mutant in _mutants(source)]
        killed = 0
        if tests:
            _, _, elapsed = _pytest(tests, copy, copy, _UNMUTATED_TIMEOUT, ["--noconftest"])
            timeout = max(2.0, 10 * elapsed)
            for path, source, mutant in mutants:
                path.write_text(mutant, encoding="utf-8")
                code, _, _ = _pytest(tests, copy, copy, timeout, ["--noconftest", "-x"])
                killed += code != 0
                path.write_text(source, encoding="utf-8")
    return killed / len(mutants) if mutants else 1.0


# ---------------------------------------------------------------- verify


def verify(component_id: str, repo_root: Path, judge=None, test_author=None) -> VerificationReport:
    repo_root = Path(repo_root).resolve()
    slug = component_id.removeprefix("comp-")
    module_name = slug.replace("-", "_")
    spec_dir = repo_root / "specs" / "components" / slug
    verification_dir = repo_root / "verification" / slug
    front = (spec_dir / "component.md").read_text(encoding="utf-8").split("\n---", 1)[0]
    sealed = re.search(r"^sealed: *true *$", front, re.M) is not None
    if sealed:
        code_dir = repo_root / re.search(r"^source_path: *(\S+)", front, re.M).group(1)
    else:
        code_dir = repo_root / "gen" / slug

    modules = {}

    def dependency(rel, name):
        key = (repo_root, name)
        if key not in modules:
            modules[key] = _load_dependency(repo_root, rel, name)
        return modules[key]

    def bundle_for(criterion_id):
        assembler = dependency("gen/spec-bundle-assembler", "spec_bundle_assembler")
        return assembler.assemble_criterion(component_id, criterion_id, repo_root)

    parsed = _parse_criteria(spec_dir / "acceptance")
    drift = _interface_drift(spec_dir, code_dir, module_name)

    outputs = {}
    if not sealed and any(c["kind"] == "compiled" for c in parsed):
        compiler = dependency("pipeline/criterion-compiler", "criterion_compiler")
        report = compiler.compile(component_id, repo_root)
        outputs = {_get(o, "criterion_id"): o for o in _get(report, "outputs")}
    characterization = _characterization_tests(verification_dir) if sealed else []

    criteria = []
    generated_tests = []
    with tempfile.TemporaryDirectory() as author_dir:
        for c in parsed:
            entry = {"id": c["id"], "covers": c["covers"], "kind": c["kind"]}
            if c["kind"] == "llm-judge":
                entry.update(_judge(judge, bundle_for, c["id"]))
            elif sealed:
                entry.update(_characterize(characterization, c["id"], code_dir, repo_root))
            elif c["kind"] == "compiled":
                output = outputs.get(c["id"], {"message": "no compiled output"})
                if _get(output, "status") == "compiled":
                    entry.update(_run_check([repo_root / _get(output, "file")], code_dir, repo_root))
                else:
                    entry.update(_fail(_get(output, "message")))
            else:
                cached = verification_dir / "generated-test" / (
                    "test_" + c["id"].lower().replace("-", "_") + ".py"
                )
                path, authoring, error = _generated_test(
                    c["id"], cached, Path(author_dir), test_author, bundle_for
                )
                if path is None:
                    entry.update(_fail(error))
                else:
                    generated_tests.append(path)
                    entry.update(_run_check([path], code_dir, repo_root))
                if authoring is not None:
                    entry["test_authoring"] = authoring
            criteria.append(entry)

        generated = [c for c in parsed if c["kind"] == "generated-test"]
        score = None
        if generated and not sealed:
            score = _mutation_score(code_dir, generated_tests)

    threshold = 0.9 if any(c["freeform"] for c in generated) else 0.8

    requirement_results = {}
    for entry in criteria:
        prior = requirement_results.get(entry["covers"], "pass")
        requirement_results[entry["covers"]] = (
            "pass" if prior == "pass" and entry["result"] == "pass" else "fail"
        )

    failed = (
        drift
        or any(entry["result"] == "fail" for entry in criteria)
        or (score is not None and score < threshold)
    )
    return VerificationReport(
        component_id=component_id,
        criteria=criteria,
        requirement_results=dict(sorted(requirement_results.items())),
        interface_drift=drift,
        mutation_score=score,
        overall="fail" if failed else "pass",
    )


# ---------------------------------------------------------------- CLI


def _usage():
    print(_USAGE, file=sys.stderr)
    return 2


def main(argv):
    args = list(argv)
    component_id = None
    values = {"--repo-root": ".", "--format": "text"}
    i = 0
    while i < len(args):
        arg = args[i]
        flag, eq, value = arg.partition("=")
        if flag in values and eq:
            values[flag] = value
        elif arg in values and i + 1 < len(args):
            values[arg] = args[i + 1]
            i += 1
        elif component_id is None and not arg.startswith("-"):
            component_id = arg
        else:
            return _usage()
        i += 1
    if component_id is None or values["--format"] not in ("json", "text"):
        return _usage()
    repo_root = Path(values["--repo-root"])
    slug = component_id.removeprefix("comp-")
    if not (repo_root / "specs" / "components" / slug / "component.md").is_file():
        return _usage()
    report = verify(component_id, repo_root)
    if values["--format"] == "json":
        print(json.dumps(report.to_dict(), indent=2, default=str))
    else:
        print(f"{report.component_id}: {report.overall}")
        for entry in report.criteria:
            print(f"  {entry['id']}: {entry['result']}")
    return 0 if report.overall == "pass" else 1
