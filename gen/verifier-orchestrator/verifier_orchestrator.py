"""Verifier Orchestrator: dispatches acceptance criteria to the right
checking mechanism and produces one VerificationReport."""
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
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

GATE_VERSION = "verifier-orchestrator@2.0.0"

_DEFAULT_TIMEOUT = 10.0
MUTATION_THRESHOLD = 0.8

_SPEC_BUNDLE_ASSEMBLER_PATH = ("gen", "spec-bundle-assembler")
_SPEC_BUNDLE_ASSEMBLER_MODULE = "spec_bundle_assembler"
_CRITERION_COMPILER_PATH = ("pipeline", "criterion-compiler")
_CRITERION_COMPILER_MODULE = "criterion_compiler"

_USAGE = (
    "usage: hotdocs verify-component <component-id> "
    "[--repo-root=<dir>] [--format=json|text]"
)


# ---------------------------------------------------------------------------
# Dual dict-or-attribute access
# ---------------------------------------------------------------------------

def _get(obj: Any, key: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


# ---------------------------------------------------------------------------
# Dynamic module loading (R-VERIFY-013)
# ---------------------------------------------------------------------------

_MODULE_CACHE: Dict[Any, Any] = {}


def _load_module(repo_root: Path, module_dir: Path, module_name: str):
    key = (str(Path(repo_root).resolve()), module_name)
    cached = _MODULE_CACHE.get(key)
    if cached is not None:
        return cached
    module_dir = Path(module_dir)
    init_file = module_dir / "__init__.py"
    if init_file.is_file():
        file_path = init_file
        search_locations = [str(module_dir)]
    else:
        file_path = module_dir / (module_name + ".py")
        search_locations = None
    load_name = "_verifier_orchestrator_loaded__%s__%d" % (module_name, abs(hash(key)))
    spec = importlib.util.spec_from_file_location(
        load_name, str(file_path), submodule_search_locations=search_locations
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[load_name] = module
    spec.loader.exec_module(module)
    _MODULE_CACHE[key] = module
    return module


def _load_spec_bundle_assembler(repo_root: Path):
    module_dir = repo_root
    for part in _SPEC_BUNDLE_ASSEMBLER_PATH:
        module_dir = module_dir / part
    return _load_module(repo_root, module_dir, _SPEC_BUNDLE_ASSEMBLER_MODULE)


def _load_criterion_compiler(repo_root: Path):
    module_dir = repo_root
    for part in _CRITERION_COMPILER_PATH:
        module_dir = module_dir / part
    return _load_module(repo_root, module_dir, _CRITERION_COMPILER_MODULE)


# ---------------------------------------------------------------------------
# Acceptance criteria parsing
# ---------------------------------------------------------------------------

@dataclass
class _CriterionSpec:
    id: str
    covers: str
    kind: str
    gherkin: str
    file: str


_HEADING_RE = re.compile(r"^#\s*(AC-[A-Za-z0-9-]+)\s*$", re.MULTILINE)
_COVERS_RE = re.compile(
    r"^\s*(?:\*\*)?Covers(?:\*\*)?:\s*(R-[A-Za-z0-9-]+)", re.MULTILINE | re.IGNORECASE
)
_KIND_RE = re.compile(
    r"^\s*(?:\*\*)?Kind(?:\*\*)?:\s*(compiled|generated-test|llm-judge)",
    re.MULTILINE | re.IGNORECASE,
)


def _parse_acceptance_file(text: str, path: Path) -> Optional[_CriterionSpec]:
    heading_match = _HEADING_RE.search(text)
    if not heading_match:
        return None
    criterion_id = heading_match.group(1)
    covers_match = _COVERS_RE.search(text)
    covers = covers_match.group(1) if covers_match else ""
    kind_match = _KIND_RE.search(text)
    kind = kind_match.group(1).lower() if kind_match else ""
    return _CriterionSpec(id=criterion_id, covers=covers, kind=kind, gherkin=text, file=str(path))


def _parse_acceptance_dir(acceptance_dir: Path) -> List[_CriterionSpec]:
    criteria = []
    if not acceptance_dir.is_dir():
        return criteria
    for f in sorted(acceptance_dir.glob("*.md")):
        parsed = _parse_acceptance_file(f.read_text(encoding="utf-8"), f)
        if parsed is not None:
            criteria.append(parsed)
    return criteria


def _slug(component_id: str) -> str:
    return component_id[len("comp-"):] if component_id.startswith("comp-") else component_id


_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def _read_frontmatter(path: Path) -> Dict[str, str]:
    if not path.is_file():
        return {}
    text = path.read_text(encoding="utf-8")
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return {}
    data: Dict[str, str] = {}
    for line in match.group(1).splitlines():
        line = line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, _, value = line.partition(":")
        data[key.strip()] = value.strip().strip('"').strip("'")
    return data


def _criterion_test_filename(criterion_id: str) -> str:
    return "test_" + criterion_id.lower().replace("-", "_") + ".py"


# ---------------------------------------------------------------------------
# Test execution with timeout (R-VERIFY-014)
# ---------------------------------------------------------------------------

def _kill_process_tree(proc: "subprocess.Popen") -> None:
    try:
        if os.name == "posix":
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        else:
            proc.kill()
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


def _run_test_suite(targets: List[Any], directory: Path, timeout: float):
    env = os.environ.copy()
    env["PYTHONPATH"] = str(directory)
    args = [sys.executable, "-m", "pytest", "-q"] + [str(t) for t in targets]
    start = time.monotonic()
    proc = subprocess.Popen(
        args,
        cwd=str(directory),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        start_new_session=(os.name == "posix"),
    )
    timed_out = False
    try:
        raw, _ = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        _kill_process_tree(proc)
        raw, _ = proc.communicate()
    duration = time.monotonic() - start
    output = raw.decode("utf-8", errors="replace") if raw else ""
    passed = (proc.returncode == 0) and not timed_out
    return passed, duration, timed_out, output


# ---------------------------------------------------------------------------
# failure_detail parsing (R-VERIFY-012)
# ---------------------------------------------------------------------------

_ASSERT_LINE_RE = re.compile(r"^E\s+assert\s+(.*)$", re.MULTILINE)
_CMP_OPS = ["==", "!=", ">=", "<=", " is not ", " is ", " not in ", " in ", ">", "<"]


def _try_literal(text: str) -> Any:
    text = text.strip()
    try:
        return ast.literal_eval(text)
    except Exception:
        return text


def _parse_pytest_failure(output: str):
    match = _ASSERT_LINE_RE.search(output or "")
    if not match:
        lines = [l for l in (output or "").splitlines() if l.strip()]
        message = lines[-1].strip() if lines else "test failed"
        return message, None, None
    assert_expr = match.group(1).strip()
    message = "assert %s" % assert_expr
    for op in _CMP_OPS:
        if op in assert_expr:
            left, _, right = assert_expr.partition(op)
            return message, _try_literal(right), _try_literal(left)
    return message, None, None


def _fail_criterion_dict(crit: _CriterionSpec, message: str, expected: Any, actual: Any) -> Dict[str, Any]:
    return {
        "id": crit.id,
        "covers": crit.covers,
        "kind": crit.kind,
        "result": "fail",
        "failure_detail": {"message": message, "expected": expected, "actual": actual},
    }


def _pass_criterion_dict(crit: _CriterionSpec) -> Dict[str, Any]:
    return {"id": crit.id, "covers": crit.covers, "kind": crit.kind, "result": "pass"}


# ---------------------------------------------------------------------------
# llm-judge dispatch (R-VERIFY-003)
# ---------------------------------------------------------------------------

def _interpret_judge_outcome(outcome: Any):
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
    if isinstance(result, bool):
        result = "pass" if result else "fail"
    if result not in ("pass", "fail", "skipped"):
        result = "fail"
    return result, rationale


def _verify_llm_judge_criteria(
    specs: List[_CriterionSpec], component_id: str, repo_root: Path, judge, assembler_mod
) -> Dict[str, Dict[str, Any]]:
    results: Dict[str, Dict[str, Any]] = {}
    for crit in specs:
        if judge is None:
            results[crit.id] = {
                "id": crit.id, "covers": crit.covers, "kind": "llm-judge",
                "result": "skipped", "rationale": None,
            }
            continue
        bundle = assembler_mod.assemble_criterion(component_id, crit.id, repo_root)
        outcome = judge(bundle)
        result, rationale = _interpret_judge_outcome(outcome)
        results[crit.id] = {
            "id": crit.id, "covers": crit.covers, "kind": "llm-judge",
            "result": result, "rationale": rationale,
        }
    return results


# ---------------------------------------------------------------------------
# compiled dispatch (R-VERIFY-001)
# ---------------------------------------------------------------------------

def _verify_compiled_criteria(
    specs: List[_CriterionSpec], component_id: str, repo_root: Path, slug: str,
    candidate_dir: Path, compiler_mod, timeout: float,
) -> Dict[str, Dict[str, Any]]:
    results: Dict[str, Dict[str, Any]] = {}
    out_dir = repo_root / "verification" / slug / "compiled"
    compile_report = compiler_mod.compile(component_id, repo_root, target="pytest", out_dir=out_dir)
    outputs = _get(compile_report, "outputs", []) or []
    outputs_by_id = {}
    for o in outputs:
        outputs_by_id[_get(o, "criterion_id")] = o
    for crit in specs:
        output = outputs_by_id.get(crit.id)
        if output is None:
            results[crit.id] = _fail_criterion_dict(crit, "criterion not found in compiled output", None, None)
            continue
        status = _get(output, "status")
        if status == "error":
            msg = _get(output, "message", "compile error")
            results[crit.id] = _fail_criterion_dict(crit, msg, None, None)
            continue
        file_value = _get(output, "file")
        file_path = Path(file_value)
        if not file_path.is_absolute():
            file_path = repo_root / file_path
        passed, _duration, timed_out, output_text = _run_test_suite([file_path], candidate_dir, timeout)
        if passed:
            results[crit.id] = _pass_criterion_dict(crit)
        else:
            message, expected, actual = _parse_pytest_failure(output_text)
            if timed_out:
                message = "test run timed out"
            results[crit.id] = _fail_criterion_dict(crit, message, expected, actual)
    return results


# ---------------------------------------------------------------------------
# generated-test dispatch (R-VERIFY-002/009/010)
# ---------------------------------------------------------------------------

def _verify_generated_test_criteria(
    specs: List[_CriterionSpec], component_id: str, repo_root: Path, slug: str,
    candidate_dir: Path, test_author, assembler_mod, timeout: float,
):
    results: Dict[str, Dict[str, Any]] = {}
    used_files: List[Path] = []
    gt_dir = repo_root / "verification" / slug / "generated-test"
    for crit in specs:
        test_path = gt_dir / _criterion_test_filename(crit.id)
        test_authoring = None
        if not test_path.is_file():
            if test_author is None:
                results[crit.id] = _fail_criterion_dict(
                    crit, "no cached test and no test_author configured", None, None
                )
                continue
            bundle = assembler_mod.assemble_criterion(component_id, crit.id, repo_root)
            outcome = test_author(bundle)
            model_call_error = _get(outcome, "model_call_error")
            if model_call_error:
                err_msg = _get(model_call_error, "message")
                if err_msg is None:
                    err_msg = str(model_call_error)
                results[crit.id] = _fail_criterion_dict(
                    crit, "test_author model call error: %s" % err_msg, None, None
                )
                continue
            file_info = _get(outcome, "file")
            content = _get(file_info, "content", "") or ""
            gt_dir.mkdir(parents=True, exist_ok=True)
            test_path.write_text(content, encoding="utf-8")
            test_authoring = {
                "model": _get(outcome, "model"),
                "seed": _get(outcome, "seed"),
                "prompt_version": _get(outcome, "prompt_version"),
                "cache_hit": bool(_get(outcome, "cache_hit", False)),
            }
        used_files.append(test_path)
        passed, _duration, timed_out, output_text = _run_test_suite([test_path], candidate_dir, timeout)
        if passed:
            entry = _pass_criterion_dict(crit)
        else:
            message, expected, actual = _parse_pytest_failure(output_text)
            if timed_out:
                message = "test run timed out"
            entry = _fail_criterion_dict(crit, message, expected, actual)
        if test_authoring is not None:
            entry["test_authoring"] = test_authoring
        results[crit.id] = entry
    return results, used_files


# ---------------------------------------------------------------------------
# sealed component characterization (R-VERIFY-017)
# ---------------------------------------------------------------------------

def _verify_sealed_criterion(crit: _CriterionSpec, verif_dir: Path, candidate_dir: Path, timeout: float) -> Dict[str, Any]:
    test_files = sorted(verif_dir.glob("test_*.py")) if verif_dir.is_dir() else []
    prefix = "test_" + crit.id.lower().replace("-", "_")
    matches: List[Any] = []
    for f in test_files:
        try:
            tree = ast.parse(f.read_text(encoding="utf-8"))
        except (SyntaxError, OSError):
            continue
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name == prefix or node.name.startswith(prefix + "_"):
                    matches.append((f, node.name))
    if not matches:
        return _fail_criterion_dict(crit, "no characterization test", None, None)
    all_passed = True
    last_output = ""
    for f, name in matches:
        node_id = "%s::%s" % (f, name)
        passed, _duration, timed_out, output = _run_test_suite([node_id], candidate_dir, timeout)
        if not passed:
            all_passed = False
            last_output = output
            if timed_out:
                last_output = "test run timed out"
    if all_passed:
        return _pass_criterion_dict(crit)
    message, expected, actual = _parse_pytest_failure(last_output)
    return _fail_criterion_dict(crit, message, expected, actual)


# ---------------------------------------------------------------------------
# interface drift check (R-VERIFY-004)
# ---------------------------------------------------------------------------

_CODE_BLOCK_RE = re.compile(r"```(?:[A-Za-z]*)\n(.*?)```", re.DOTALL)
_CALLABLE_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\(([^)]*)\)", re.MULTILINE)


def _parse_param_names(params_raw: str) -> List[str]:
    params_raw = params_raw.strip()
    if not params_raw:
        return []
    parts = []
    depth = 0
    current = ""
    for ch in params_raw:
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
        if part in ("*", "/"):
            continue
        if part.startswith("**"):
            names.append(part[2:].split(":")[0].split("=")[0].strip())
        elif part.startswith("*"):
            names.append(part[1:].split(":")[0].split("=")[0].strip())
        else:
            name = part.split(":")[0].split("=")[0].strip()
            if name:
                names.append(name)
    return names


def _extract_documented_callables(md_text: str) -> Dict[str, List[str]]:
    callables: Dict[str, List[str]] = {}
    for block in _CODE_BLOCK_RE.findall(md_text):
        for match in _CALLABLE_RE.finditer(block):
            name, params_raw = match.group(1), match.group(2)
            callables[name] = _parse_param_names(params_raw)
    return callables


def _check_interface_drift(comp_dir: Path, candidate_dir: Path, module_name: str, repo_root: Path) -> bool:
    documented: Dict[str, List[str]] = {}
    for fname in ("library.md", "cli.md"):
        f = comp_dir / "interface" / fname
        if f.is_file():
            documented.update(_extract_documented_callables(f.read_text(encoding="utf-8")))
    if not documented:
        return False
    try:
        module = _load_module(repo_root, candidate_dir, module_name)
    except Exception:
        return True
    drift = False
    for name, params in documented.items():
        obj = getattr(module, name, None)
        if obj is None or not callable(obj):
            drift = True
            continue
        try:
            sig = inspect.signature(obj)
        except (TypeError, ValueError):
            continue
        actual_params = list(sig.parameters.keys())
        if actual_params != params:
            drift = True
    return drift


# ---------------------------------------------------------------------------
# mutation testing (R-VERIFY-006)
# ---------------------------------------------------------------------------

_CMP_SWAP = {
    ast.Eq: ast.NotEq, ast.NotEq: ast.Eq,
    ast.Lt: ast.GtE, ast.GtE: ast.Lt,
    ast.Gt: ast.LtE, ast.LtE: ast.Gt,
    ast.Is: ast.IsNot, ast.IsNot: ast.Is,
    ast.In: ast.NotIn, ast.NotIn: ast.In,
}
_ARITH_SWAP = {
    ast.Add: ast.Sub, ast.Sub: ast.Add,
    ast.Mult: ast.Div, ast.Div: ast.Mult,
    ast.FloorDiv: ast.Mod, ast.Mod: ast.FloorDiv,
}


def _classify_site(node: ast.AST) -> Optional[str]:
    if isinstance(node, ast.Compare) and len(node.ops) == 1 and type(node.ops[0]) in _CMP_SWAP:
        return "compare"
    if isinstance(node, ast.BoolOp) and isinstance(node.op, (ast.And, ast.Or)):
        return "boolop"
    if isinstance(node, ast.BinOp) and type(node.op) in _ARITH_SWAP:
        return "binop"
    if isinstance(node, ast.Constant) and isinstance(node.value, bool):
        return "boolconst"
    return None


def _find_mutation_sites(tree: ast.AST) -> List[ast.AST]:
    return [n for n in ast.walk(tree) if _classify_site(n) is not None]


def _apply_mutation(tree: ast.AST, site_index: int) -> bool:
    index = 0
    for node in ast.walk(tree):
        kind = _classify_site(node)
        if kind is None:
            continue
        if index == site_index:
            if kind == "compare":
                node.ops[0] = _CMP_SWAP[type(node.ops[0])]()
            elif kind == "boolop":
                node.op = ast.Or() if isinstance(node.op, ast.And) else ast.And()
            elif kind == "binop":
                node.op = _ARITH_SWAP[type(node.op)]()
            elif kind == "boolconst":
                node.value = not node.value
            ast.fix_missing_locations(tree)
            return True
        index += 1
    return False


def _collect_py_files(directory: Path) -> List[Path]:
    if not directory.is_dir():
        return []
    return [p for p in sorted(directory.rglob("*.py")) if "__pycache__" not in p.parts]


def _compute_mutation_score(test_files: List[Path], candidate_dir: Path, timeout_floor: float) -> Optional[float]:
    if not test_files:
        return None
    py_files = _collect_py_files(candidate_dir)
    sources: Dict[Path, str] = {}
    site_counts: Dict[Path, int] = {}
    total_sites = 0
    for f in py_files:
        try:
            src = f.read_text(encoding="utf-8")
            tree = ast.parse(src)
        except (SyntaxError, OSError):
            continue
        n = len(_find_mutation_sites(tree))
        if n:
            sources[f] = src
            site_counts[f] = n
            total_sites += n
    if total_sites == 0:
        return 1.0

    _passed, baseline_duration, _timed_out, _out = _run_test_suite(test_files, candidate_dir, timeout_floor)
    mutant_timeout = max(timeout_floor, 10.0 * baseline_duration)

    killed = 0
    for f, n in site_counts.items():
        for site_index in range(n):
            tmp_dir = tempfile.mkdtemp(prefix="vo-mutant-")
            try:
                sandbox = Path(tmp_dir) / "sandbox"
                shutil.copytree(candidate_dir, sandbox)
                tree = ast.parse(sources[f])
                _apply_mutation(tree, site_index)
                mutated_src = ast.unparse(tree)
                rel = f.relative_to(candidate_dir)
                (sandbox / rel).write_text(mutated_src, encoding="utf-8")
                passed, _d, timed_out, _o = _run_test_suite(test_files, sandbox, mutant_timeout)
                if timed_out or not passed:
                    killed += 1
            finally:
                shutil.rmtree(tmp_dir, ignore_errors=True)
    return killed / total_sites


# ---------------------------------------------------------------------------
# requirement_results projection (R-VERIFY-011) / overall (R-VERIFY-005/017)
# ---------------------------------------------------------------------------

def _project_requirement_results(criteria: List[Dict[str, Any]]) -> Dict[str, str]:
    req_results: Dict[str, str] = {}
    for c in criteria:
        rid = c.get("covers")
        if not rid:
            continue
        if rid not in req_results:
            req_results[rid] = "pass"
        if c.get("result") != "pass":
            req_results[rid] = "fail"
    return req_results


def _compute_overall(
    criteria: List[Dict[str, Any]], interface_drift: bool, mutation_score: Optional[float], sealed: bool
) -> str:
    for c in criteria:
        kind = c.get("kind")
        result = c.get("result")
        if kind in ("compiled", "generated-test") and result == "fail":
            return "fail"
        if kind == "llm-judge" and result == "fail":
            return "fail"
    if interface_drift:
        return "fail"
    if not sealed and mutation_score is not None and mutation_score < MUTATION_THRESHOLD:
        return "fail"
    return "pass"


# ---------------------------------------------------------------------------
# VerificationReport (R-VERIFY-007)
# ---------------------------------------------------------------------------

@dataclass
class VerificationReport:
    component_id: str
    criteria: List[Dict[str, Any]]
    requirement_results: Dict[str, str]
    interface_drift: bool
    mutation_score: Optional[float]
    overall: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "component_id": self.component_id,
            "criteria": self.criteria,
            "requirement_results": self.requirement_results,
            "interface_drift": self.interface_drift,
            "mutation_score": self.mutation_score,
            "overall": self.overall,
        }


# ---------------------------------------------------------------------------
# verify()
# ---------------------------------------------------------------------------

def verify(component_id: str, repo_root: Path, judge=None, test_author=None) -> VerificationReport:
    repo_root = Path(repo_root)
    slug = _slug(component_id)
    comp_dir = repo_root / "specs" / "components" / slug
    frontmatter = _read_frontmatter(comp_dir / "component.md")
    sealed = str(frontmatter.get("sealed", "")).strip().lower() == "true"
    source_path = frontmatter.get("source_path")

    criteria_specs = _parse_acceptance_dir(comp_dir / "acceptance")
    module_name = slug.replace("-", "_")
    assembler_mod = _load_spec_bundle_assembler(repo_root)

    results: Dict[str, Dict[str, Any]] = {}

    if sealed:
        candidate_dir = (repo_root / source_path) if source_path else None
        missing = candidate_dir is None or not candidate_dir.is_dir()
        verif_dir = repo_root / "verification" / slug
        lj_specs = [c for c in criteria_specs if c.kind == "llm-judge"]
        other_specs = [c for c in criteria_specs if c.kind != "llm-judge"]
        results.update(_verify_llm_judge_criteria(lj_specs, component_id, repo_root, judge, assembler_mod))
        for crit in other_specs:
            if missing:
                results[crit.id] = _fail_criterion_dict(crit, "source_path directory not found", None, None)
            else:
                results[crit.id] = _verify_sealed_criterion(crit, verif_dir, candidate_dir, _DEFAULT_TIMEOUT)
        interface_drift = True if missing else _check_interface_drift(comp_dir, candidate_dir, module_name, repo_root)
        mutation_score = None
    else:
        candidate_dir = repo_root / "gen" / slug
        compiled_specs = [c for c in criteria_specs if c.kind == "compiled"]
        gt_specs = [c for c in criteria_specs if c.kind == "generated-test"]
        lj_specs = [c for c in criteria_specs if c.kind == "llm-judge"]

        if compiled_specs:
            compiler_mod = _load_criterion_compiler(repo_root)
            results.update(
                _verify_compiled_criteria(
                    compiled_specs, component_id, repo_root, slug, candidate_dir, compiler_mod, _DEFAULT_TIMEOUT
                )
            )

        gt_results, used_files = _verify_generated_test_criteria(
            gt_specs, component_id, repo_root, slug, candidate_dir, test_author, assembler_mod, _DEFAULT_TIMEOUT
        )
        results.update(gt_results)

        results.update(_verify_llm_judge_criteria(lj_specs, component_id, repo_root, judge, assembler_mod))

        interface_drift = _check_interface_drift(comp_dir, candidate_dir, module_name, repo_root)
        mutation_score = _compute_mutation_score(used_files, candidate_dir, _DEFAULT_TIMEOUT) if gt_specs else None

    criteria = [results[c.id] for c in criteria_specs if c.id in results]
    requirement_results = _project_requirement_results(criteria)
    overall = _compute_overall(criteria, interface_drift, mutation_score, sealed)

    return VerificationReport(
        component_id=component_id,
        criteria=criteria,
        requirement_results=requirement_results,
        interface_drift=interface_drift,
        mutation_score=mutation_score,
        overall=overall,
    )


# ---------------------------------------------------------------------------
# CLI (R-VERIFY-018)
# ---------------------------------------------------------------------------

def main(argv: Optional[List[str]] = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    args = list(argv)

    if not args or args[0].startswith("--"):
        print(_USAGE, file=sys.stderr)
        return 2

    component_id = args[0]
    repo_root = Path.cwd()
    fmt = "text"

    i = 1
    while i < len(args):
        arg = args[i]
        if arg == "--repo-root" or arg.startswith("--repo-root="):
            if "=" in arg:
                value = arg.split("=", 1)[1]
                i += 1
            else:
                if i + 1 >= len(args):
                    print(_USAGE, file=sys.stderr)
                    return 2
                value = args[i + 1]
                i += 2
            repo_root = Path(value)
        elif arg == "--format" or arg.startswith("--format="):
            if "=" in arg:
                value = arg.split("=", 1)[1]
                i += 1
            else:
                if i + 1 >= len(args):
                    print(_USAGE, file=sys.stderr)
                    return 2
                value = args[i + 1]
                i += 2
            fmt = value
        else:
            print(_USAGE, file=sys.stderr)
            return 2

    if fmt not in ("json", "text"):
        print(_USAGE, file=sys.stderr)
        return 2

    slug = _slug(component_id)
    if not (repo_root / "specs" / "components" / slug / "component.md").is_file():
        print(_USAGE, file=sys.stderr)
        return 2

    report = verify(component_id, repo_root)

    if fmt == "json":
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print("%s: %s" % (report.component_id, report.overall))
        for c in report.criteria:
            print("  %s: %s" % (c["id"], c["result"]))

    return 0 if report.overall == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())