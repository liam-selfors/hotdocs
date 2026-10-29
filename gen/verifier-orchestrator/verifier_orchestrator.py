from __future__ import annotations

import argparse
import ast
import importlib.util
import inspect
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path

_MUTATION_SCORE_THRESHOLD = 0.8

_MODULE_CACHE: dict = {}

_COVERS_RE = re.compile(r'^Covers:\s*(.+?)\s*$', re.MULTILINE | re.IGNORECASE)
_KIND_RE = re.compile(r'^Kind:\s*(\S+)\s*$', re.MULTILINE | re.IGNORECASE)
_ID_RE = re.compile(r'\bAC-[A-Z0-9]+(?:-[A-Z0-9]+)*\b')

_SIGNATURE_RE = re.compile(r'^([A-Za-z_][A-Za-z0-9_]*)\(([^)]*)\)')

_ASSERT_LINE_RE = re.compile(r'^E\s+assert\s+(.*)$')
_EQ_RE = re.compile(r'^(.*?)\s*==\s*(.*)$')
_NEQ_RE = re.compile(r'^(.*?)\s*!=\s*(.*)$')
_IN_RE = re.compile(r'^(.*?)\s+in\s+(.*)$')

_COMPARISON_MUTATIONS = {
    ast.Eq: ast.NotEq, ast.NotEq: ast.Eq,
    ast.Lt: ast.GtE, ast.LtE: ast.Gt, ast.Gt: ast.LtE, ast.GtE: ast.Lt,
}
_BOOLOP_MUTATIONS = {ast.And: ast.Or, ast.Or: ast.And}
_ARITH_MUTATIONS = {ast.Add: ast.Sub, ast.Sub: ast.Add, ast.Mult: ast.Div, ast.Div: ast.Mult}


@dataclass
class VerificationReport:
    component_id: str
    criteria: list = field(default_factory=list)
    requirement_results: dict = field(default_factory=dict)
    interface_drift: bool = False
    mutation_score: float = 1.0
    overall: str = "pass"

    def to_dict(self) -> dict:
        return asdict(self)


def _slug(component_id: str) -> str:
    return component_id[len("comp-"):] if component_id.startswith("comp-") else component_id


def _get_attr_or_key(obj, name, default=None):
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _get_file_info(outcome):
    file_obj = _get_attr_or_key(outcome, "file")
    if file_obj is None:
        return None, None
    if isinstance(file_obj, dict):
        return file_obj.get("path"), file_obj.get("content")
    return getattr(file_obj, "path", None), getattr(file_obj, "content", None)


def _coerce_result(value) -> str:
    if isinstance(value, bool):
        return "pass" if value else "fail"
    if isinstance(value, str):
        v = value.strip().lower()
        if v in ("pass", "fail", "skipped"):
            return v
        if v in ("true", "yes"):
            return "pass"
        if v in ("false", "no"):
            return "fail"
    return "pass" if value else "fail"


def _normalize_judge_outcome(outcome):
    if isinstance(outcome, dict):
        result = outcome.get("result", outcome.get("verdict"))
        rationale = outcome.get("rationale")
    elif hasattr(outcome, "result") or hasattr(outcome, "verdict"):
        result = getattr(outcome, "result", None)
        if result is None:
            result = getattr(outcome, "verdict", None)
        rationale = getattr(outcome, "rationale", None)
    else:
        result = outcome
        rationale = None
    return _coerce_result(result), rationale


# ---- acceptance criteria parsing ----

def _parse_acceptance_dir(acceptance_dir: Path) -> list:
    if not acceptance_dir.is_dir():
        return []
    criteria = []
    for path in sorted(acceptance_dir.glob("*.md")):
        text = path.read_text()
        covers_match = _COVERS_RE.search(text)
        kind_match = _KIND_RE.search(text)
        id_match = _ID_RE.search(text)
        criterion_id = id_match.group(0) if id_match else path.stem.upper().replace("_", "-")
        covers = covers_match.group(1).strip() if covers_match else ""
        kind = kind_match.group(1).strip().lower() if kind_match else ""
        criteria.append({
            "criterion_id": criterion_id, "covers": covers, "kind": kind,
            "gherkin": text, "file": str(path),
        })
    return criteria


# ---- dynamic module loading (R-VERIFY-013: keyed by (repo_root, module_name)) ----

def _locate_module_file(base_dir: Path, module_name: str):
    flat = base_dir / f"{module_name}.py"
    if flat.is_file():
        return flat, False
    pkg_init = base_dir / module_name / "__init__.py"
    if pkg_init.is_file():
        return pkg_init, True
    raise FileNotFoundError(f"no module '{module_name}' found under {base_dir}")


def _load_module(module_file: Path, module_name: str, repo_root: Path, is_package: bool = False):
    key = (repo_root, module_name)
    cached = _MODULE_CACHE.get(key)
    if cached is not None:
        return cached
    if is_package:
        spec = importlib.util.spec_from_file_location(
            module_name, module_file, submodule_search_locations=[str(module_file.parent)]
        )
    else:
        spec = importlib.util.spec_from_file_location(module_name, module_file)
    module = importlib.util.module_from_spec(spec)
    # Must register before exec_module: dataclasses in the loaded module look
    # up sys.modules[cls.__module__] while their own class body executes.
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    _MODULE_CACHE[key] = module
    return module


def _load_criterion_compiler(repo_root: Path):
    base_dir = repo_root / "pipeline" / "criterion-compiler"
    module_file, is_package = _locate_module_file(base_dir, "criterion_compiler")
    return _load_module(module_file, "criterion_compiler", repo_root, is_package)


def _load_spec_bundle_assembler(repo_root: Path):
    base_dir = repo_root / "gen" / "spec-bundle-assembler"
    module_file, is_package = _locate_module_file(base_dir, "spec_bundle_assembler")
    return _load_module(module_file, "spec_bundle_assembler", repo_root, is_package)


# ---- pytest execution ----

def _run_pytest(test_files, pythonpath: Path) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(pythonpath)
    args = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"]
    args.extend(str(f) for f in test_files)
    return subprocess.run(args, capture_output=True, text=True, env=env)


def _safe_literal_eval(text: str):
    try:
        return ast.literal_eval(text.strip())
    except (ValueError, SyntaxError):
        return None


def _extract_failure_detail(stdout: str) -> dict:
    assert_text = None
    for line in stdout.splitlines():
        m = _ASSERT_LINE_RE.match(line.strip())
        if m:
            assert_text = m.group(1).strip()
    if assert_text is None:
        lines = [l for l in stdout.splitlines() if l.strip()]
        message = lines[-1].strip() if lines else "test failed"
        return {"message": message, "expected": None, "actual": None}
    expected = None
    actual = None
    for pattern in (_EQ_RE, _NEQ_RE, _IN_RE):
        m = pattern.match(assert_text)
        if m:
            actual = _safe_literal_eval(m.group(1))
            expected = _safe_literal_eval(m.group(2))
            break
    return {"message": f"assert {assert_text}", "expected": expected, "actual": actual}


# ---- interface drift check (R-VERIFY-004) ----

def _parse_param_names(params_text: str) -> list:
    parts = []
    depth = 0
    current = ""
    for ch in params_text:
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append(current)
            current = ""
        else:
            current += ch
    if current.strip():
        parts.append(current)
    names = []
    for part in parts:
        part = part.strip()
        if not part or part in ("*", "/"):
            continue
        part = part.lstrip("*")
        name = re.split(r'[:=]', part, maxsplit=1)[0].strip()
        if name:
            names.append(name)
    return names


def _extract_documented_callables(markdown_text: str) -> list:
    callables = []
    in_code_block = False
    for line in markdown_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            in_code_block = not in_code_block
            continue
        if not in_code_block:
            continue
        m = _SIGNATURE_RE.match(stripped)
        if not m:
            continue
        name, params_text = m.group(1), m.group(2)
        callables.append((name, _parse_param_names(params_text)))
    return callables


def _check_interface_drift(gen_dir: Path, module_name: str, interface_dir: Path, repo_root: Path) -> bool:
    try:
        module_file, is_package = _locate_module_file(gen_dir, module_name)
        module = _load_module(module_file, module_name, repo_root, is_package)
    except Exception:
        return True

    documented = []
    for filename in ("library.md", "cli.md"):
        doc_path = interface_dir / filename
        if doc_path.is_file():
            documented.extend(_extract_documented_callables(doc_path.read_text()))

    drift = False
    for name, params in documented:
        attr = getattr(module, name, None)
        if attr is None or not callable(attr):
            drift = True
            continue
        try:
            sig = inspect.signature(attr)
        except (TypeError, ValueError):
            drift = True
            continue
        if list(sig.parameters.keys()) != params:
            drift = True
    return drift


# ---- mutation testing (R-VERIFY-006: single union score per component) ----

def _is_mutable(node) -> bool:
    if isinstance(node, ast.Compare) and len(node.ops) == 1 and type(node.ops[0]) in _COMPARISON_MUTATIONS:
        return True
    if isinstance(node, ast.BoolOp) and type(node.op) in _BOOLOP_MUTATIONS:
        return True
    if isinstance(node, ast.BinOp) and type(node.op) in _ARITH_MUTATIONS:
        return True
    if isinstance(node, ast.Constant) and isinstance(node.value, bool):
        return True
    return False


def _apply_mutation(node) -> None:
    if isinstance(node, ast.Compare):
        node.ops[0] = _COMPARISON_MUTATIONS[type(node.ops[0])]()
    elif isinstance(node, ast.BoolOp):
        node.op = _BOOLOP_MUTATIONS[type(node.op)]()
    elif isinstance(node, ast.BinOp):
        node.op = _ARITH_MUTATIONS[type(node.op)]()
    elif isinstance(node, ast.Constant):
        node.value = not node.value


def _generate_mutants(source: str) -> list:
    try:
        base_tree = ast.parse(source)
    except SyntaxError:
        return []
    mutable_count = sum(1 for node in ast.walk(base_tree) if _is_mutable(node))
    mutants = []
    for index in range(mutable_count):
        tree = ast.parse(source)
        mutable_nodes = [node for node in ast.walk(tree) if _is_mutable(node)]
        _apply_mutation(mutable_nodes[index])
        ast.fix_missing_locations(tree)
        mutants.append(ast.unparse(tree))
    return mutants


def _compute_mutation_score(gen_dir: Path, module_name: str, test_files: list) -> float:
    # One score for the whole component: each mutant is generated once against
    # the whole candidate module and is "killed" if ANY generated-test file
    # fails against it -- never an average of per-criterion isolated scores.
    if not test_files:
        return 1.0
    try:
        main_file, _ = _locate_module_file(gen_dir, module_name)
    except FileNotFoundError:
        return 0.0
    source = main_file.read_text()
    mutants = _generate_mutants(source)
    if not mutants:
        return 1.0
    relative = main_file.relative_to(gen_dir)
    killed = 0
    for mutant_source in mutants:
        with tempfile.TemporaryDirectory() as tmp_dir:
            sandbox = Path(tmp_dir) / "sandbox"
            shutil.copytree(gen_dir, sandbox)
            (sandbox / relative).write_text(mutant_source)
            result = _run_pytest(test_files, sandbox)
            if result.returncode != 0:
                killed += 1
    return killed / len(mutants)


# ---- per-criterion checks ----

def _check_compiled(crit: dict, compiled_outputs: dict, repo_root: Path, gen_dir: Path) -> dict:
    criterion_id = crit["criterion_id"]
    covers = crit["covers"]
    output = compiled_outputs.get(criterion_id)
    if output is None or output.get("status") != "compiled":
        message = output.get("message") if output else "criterion-compiler produced no output for this criterion"
        return {
            "id": criterion_id, "covers": covers, "kind": "compiled", "result": "fail",
            "failure_detail": {"message": message, "expected": None, "actual": None},
        }
    test_file = repo_root / output["file"]
    result = _run_pytest([test_file], gen_dir)
    if result.returncode == 0:
        return {"id": criterion_id, "covers": covers, "kind": "compiled", "result": "pass"}
    return {
        "id": criterion_id, "covers": covers, "kind": "compiled", "result": "fail",
        "failure_detail": _extract_failure_detail(result.stdout),
    }


def _check_generated_test(crit: dict, component_id: str, slug: str, repo_root: Path, gen_dir: Path,
                           spec_bundle_assembler, test_author):
    criterion_id = crit["criterion_id"]
    covers = crit["covers"]
    filename = f"test_{criterion_id.lower().replace('-', '_')}.py"
    cached_path = repo_root / "verification" / slug / "generated-test" / filename
    test_authoring = None

    if cached_path.is_file():
        test_file = cached_path
    else:
        if test_author is None:
            entry = {
                "id": criterion_id, "covers": covers, "kind": "generated-test", "result": "fail",
                "failure_detail": {
                    "message": "no cached test and no test_author configured",
                    "expected": None, "actual": None,
                },
            }
            return entry, None

        bundle = spec_bundle_assembler.assemble_criterion(component_id, criterion_id, repo_root)
        outcome = test_author(bundle)
        model_call_error = _get_attr_or_key(outcome, "model_call_error")
        if model_call_error:
            entry = {
                "id": criterion_id, "covers": covers, "kind": "generated-test", "result": "fail",
                "failure_detail": {"message": str(model_call_error), "expected": None, "actual": None},
            }
            return entry, None

        _, file_content = _get_file_info(outcome)
        cached_path.parent.mkdir(parents=True, exist_ok=True)
        cached_path.write_text(file_content or "")
        test_file = cached_path
        test_authoring = {
            "model": _get_attr_or_key(outcome, "model"),
            "seed": _get_attr_or_key(outcome, "seed"),
            "prompt_version": _get_attr_or_key(outcome, "prompt_version"),
            "cache_hit": bool(_get_attr_or_key(outcome, "cache_hit", False)),
        }

    result = _run_pytest([test_file], gen_dir)
    entry = {
        "id": criterion_id, "covers": covers, "kind": "generated-test",
        "result": "pass" if result.returncode == 0 else "fail",
    }
    if test_authoring is not None:
        entry["test_authoring"] = test_authoring
    if entry["result"] == "fail":
        entry["failure_detail"] = _extract_failure_detail(result.stdout)
    return entry, test_file


def _check_llm_judge(crit: dict, component_id: str, repo_root: Path, spec_bundle_assembler, judge) -> dict:
    criterion_id = crit["criterion_id"]
    covers = crit["covers"]
    if judge is None:
        return {"id": criterion_id, "covers": covers, "kind": "llm-judge", "result": "skipped", "rationale": None}
    bundle = spec_bundle_assembler.assemble_criterion(component_id, criterion_id, repo_root)
    outcome = judge(bundle)
    result, rationale = _normalize_judge_outcome(outcome)
    return {"id": criterion_id, "covers": covers, "kind": "llm-judge", "result": result, "rationale": rationale}


def _build_requirement_results(criteria_entries: list) -> dict:
    coverage: dict = {}
    for entry in criteria_entries:
        covers = entry.get("covers") or ""
        for rid in (part.strip() for part in covers.split(",")):
            if not rid:
                continue
            coverage.setdefault(rid, []).append(entry["result"])
    return {
        rid: ("pass" if all(r == "pass" for r in results) else "fail")
        for rid, results in coverage.items()
    }


# ---- top-level orchestration ----

def verify(component_id: str, repo_root: Path, judge=None, test_author=None) -> VerificationReport:
    repo_root = Path(repo_root)
    slug = _slug(component_id)
    module_name = slug.replace("-", "_")
    gen_dir = repo_root / "gen" / slug
    component_dir = repo_root / "specs" / "components" / slug
    acceptance_dir = component_dir / "acceptance"
    interface_dir = component_dir / "interface"

    parsed_criteria = _parse_acceptance_dir(acceptance_dir)

    compiled_outputs: dict = {}
    if any(c["kind"] == "compiled" for c in parsed_criteria):
        criterion_compiler = _load_criterion_compiler(repo_root)
        compile_report = criterion_compiler.compile(component_id, repo_root, target="pytest")
        for output in compile_report.outputs:
            compiled_outputs[output["criterion_id"]] = output

    spec_bundle_assembler = None
    if any(c["kind"] in ("generated-test", "llm-judge") for c in parsed_criteria):
        spec_bundle_assembler = _load_spec_bundle_assembler(repo_root)

    criteria_entries = []
    generated_test_files = []

    for crit in parsed_criteria:
        kind = crit["kind"]
        if kind == "compiled":
            entry = _check_compiled(crit, compiled_outputs, repo_root, gen_dir)
        elif kind == "generated-test":
            entry, test_file = _check_generated_test(
                crit, component_id, slug, repo_root, gen_dir, spec_bundle_assembler, test_author
            )
            if test_file is not None:
                generated_test_files.append(test_file)
        elif kind == "llm-judge":
            entry = _check_llm_judge(crit, component_id, repo_root, spec_bundle_assembler, judge)
        else:
            entry = {
                "id": crit["criterion_id"], "covers": crit["covers"], "kind": kind, "result": "fail",
                "failure_detail": {
                    "message": f"unrecognized criterion kind '{kind}'", "expected": None, "actual": None,
                },
            }
        criteria_entries.append(entry)

    interface_drift = _check_interface_drift(gen_dir, module_name, interface_dir, repo_root)

    has_generated_test = any(c["kind"] == "generated-test" for c in parsed_criteria)
    mutation_score = _compute_mutation_score(gen_dir, module_name, generated_test_files) if has_generated_test else 1.0

    requirement_results = _build_requirement_results(criteria_entries)

    any_hard_fail = any(
        e["result"] == "fail" for e in criteria_entries if e["kind"] in ("compiled", "generated-test")
    )
    any_judge_fail = any(e["result"] == "fail" for e in criteria_entries if e["kind"] == "llm-judge")
    mutation_fail = has_generated_test and mutation_score < _MUTATION_SCORE_THRESHOLD

    overall = "fail" if (any_hard_fail or any_judge_fail or interface_drift or mutation_fail) else "pass"

    return VerificationReport(
        component_id=component_id,
        criteria=criteria_entries,
        requirement_results=requirement_results,
        interface_drift=interface_drift,
        mutation_score=mutation_score,
        overall=overall,
    )


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    parser = argparse.ArgumentParser(prog="hotdocs verify")
    parser.add_argument("component_id")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--format", choices=["json", "text"], default="text")
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 2

    repo_root = Path(args.repo_root).resolve()
    report = verify(args.component_id, repo_root)

    if args.format == "json":
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print(f"{report.component_id}: {report.overall}")
        for c in report.criteria:
            print(f"  {c['id']}: {c['result']}")

    return 0 if report.overall == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())