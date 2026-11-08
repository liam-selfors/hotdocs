from __future__ import annotations

import ast
import copy
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
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

GATE_VERSION = "verifier-orchestrator@2.0.0"

MUTATION_THRESHOLD = 0.8
DEFAULT_TEST_TIMEOUT = 10.0

_COMPARISON_SWAPS = {
    ast.Eq: ast.NotEq, ast.NotEq: ast.Eq,
    ast.Lt: ast.GtE, ast.GtE: ast.Lt,
    ast.Gt: ast.LtE, ast.LtE: ast.Gt,
    ast.Is: ast.IsNot, ast.IsNot: ast.Is,
    ast.In: ast.NotIn, ast.NotIn: ast.In,
}
_BOOLOP_SWAPS = {ast.And: ast.Or, ast.Or: ast.And}
_ARITH_SWAPS = {
    ast.Add: ast.Sub, ast.Sub: ast.Add,
    ast.Mult: ast.Div, ast.Div: ast.Mult,
    ast.FloorDiv: ast.Mod, ast.Mod: ast.FloorDiv,
}

_AC_HEADING_RE = re.compile(r"^#\s*(AC-[A-Z0-9]+(?:-[A-Z0-9]+)*[a-z]?)\s*$", re.MULTILINE)
_COVERS_RE = re.compile(r"Covers:\s*`?([A-Za-z0-9-]+)`?", re.IGNORECASE)
_KIND_RE = re.compile(r"kind:\s*`?(compiled|generated-test|llm-judge)`?", re.IGNORECASE)
_CODE_FENCE_RE = re.compile(r"```[a-zA-Z]*\n(.*?)```", re.DOTALL)
_SIG_LINE_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\(([^()]*)\)\s*(->.*)?$")
_ASSERT_LINE_RE = re.compile(r"assert\s+(.+?)\s*(==|!=|<=|>=|<|>)\s*(.+)")


# ---------------------------------------------------------------------------
# Dual dict-or-attribute access, used for every value read from a dependency
# call (including the dependency function's own top-level return value).
# ---------------------------------------------------------------------------

def _get(obj: Any, key: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _slug(component_id: str) -> str:
    return component_id[len("comp-"):] if component_id.startswith("comp-") else component_id


def _module_name_from_slug(slug: str) -> str:
    return slug.replace("-", "_")


# ---------------------------------------------------------------------------
# Module resolution/loading, cached strictly by (repo_root, module_name)
# (R-VERIFY-013) -- never by module_name alone.
# ---------------------------------------------------------------------------

def _tool_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if parent.name == "gen":
            return parent.parent
    raise RuntimeError(f"could not locate tool root above {here}")


def _dependency_base_dir(repo_root: Path, rel_path: str) -> Path:
    candidate = Path(repo_root) / rel_path
    if candidate.exists():
        return candidate
    return _tool_root() / rel_path


_MODULE_CACHE: dict = {}


def _load_module(repo_root: Path, base_dir: Path, module_name: str):
    cache_key = (str(Path(repo_root).resolve()), module_name)
    if cache_key in _MODULE_CACHE:
        return _MODULE_CACHE[cache_key]

    flat_file = base_dir / f"{module_name}.py"
    pkg_init = base_dir / module_name / "__init__.py"
    if flat_file.is_file():
        file_path = flat_file
        search_locations = None
    elif pkg_init.is_file():
        file_path = pkg_init
        search_locations = [str(file_path.parent)]
    else:
        raise ModuleNotFoundError(f"cannot locate module {module_name!r} under {base_dir}")

    import importlib.util as _ilu

    synthetic_name = f"_vo_loaded__{abs(hash(cache_key))}__{module_name}"
    spec = _ilu.spec_from_file_location(synthetic_name, file_path, submodule_search_locations=search_locations)
    module = _ilu.module_from_spec(spec)
    sys.modules[synthetic_name] = module
    spec.loader.exec_module(module)
    _MODULE_CACHE[cache_key] = module
    return module


def _load_dependency(repo_root: Path, rel_path: str, module_name: str):
    base_dir = _dependency_base_dir(repo_root, rel_path)
    return _load_module(repo_root, base_dir, module_name)


# ---------------------------------------------------------------------------
# component.md frontmatter + acceptance/ criteria parsing
# ---------------------------------------------------------------------------

def _read_frontmatter(path: Path) -> dict:
    if not path.is_file():
        return {}
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    block = text[3:end]
    result = {}
    for line in block.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, _, value = line.partition(":")
        value = value.strip().strip('"').strip("'")
        result[key.strip()] = value
    return result


def _parse_acceptance_criteria(acceptance_dir: Path) -> list:
    criteria = []
    if not acceptance_dir.is_dir():
        return criteria
    for path in sorted(acceptance_dir.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        heading_match = _AC_HEADING_RE.search(text)
        if not heading_match:
            continue
        criterion_id = heading_match.group(1)
        covers_match = _COVERS_RE.search(text)
        kind_match = _KIND_RE.search(text)
        criteria.append({
            "id": criterion_id,
            "covers": covers_match.group(1) if covers_match else "",
            "kind": kind_match.group(1).lower() if kind_match else "compiled",
            "gherkin": text,
            "file": str(path),
        })
    return criteria


# ---------------------------------------------------------------------------
# Interface drift (R-VERIFY-004)
# ---------------------------------------------------------------------------

def _logical_lines(block: str) -> list:
    lines = []
    current = ""
    depth = 0
    for ch in block:
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        if ch == "\n" and depth <= 0:
            if current.strip():
                lines.append(current.strip())
            current = ""
            depth = max(depth, 0)
        else:
            current += ch
    if current.strip():
        lines.append(current.strip())
    return lines


def _split_params(params_str: str) -> list:
    params = []
    depth = 0
    current = ""
    for ch in params_str:
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        if ch == "," and depth == 0:
            params.append(current.strip())
            current = ""
        else:
            current += ch
    if current.strip():
        params.append(current.strip())
    names = []
    for p in params:
        p = p.strip()
        if not p or p in ("*", "/"):
            continue
        p = p.lstrip("*")
        name = p.split(":")[0].split("=")[0].strip()
        if name:
            names.append(name)
    return names


def _extract_documented_signatures(interface_dir: Path) -> dict:
    sigs = {}
    for fname in ("library.md", "cli.md"):
        fpath = interface_dir / fname
        if not fpath.is_file():
            continue
        text = fpath.read_text(encoding="utf-8")
        for block in _CODE_FENCE_RE.findall(text):
            for logical in _logical_lines(block):
                collapsed = re.sub(r"\s+", " ", logical).strip()
                m = _SIG_LINE_RE.match(collapsed)
                if m:
                    name, params_str = m.group(1), m.group(2)
                    sigs[name] = _split_params(params_str)
    return sigs


def _check_interface_drift(repo_root: Path, slug: str, module) -> bool:
    interface_dir = Path(repo_root) / "specs" / "components" / slug / "interface"
    documented = _extract_documented_signatures(interface_dir)
    for name, doc_params in documented.items():
        attr = getattr(module, name, None)
        if attr is None or not callable(attr):
            return True
        try:
            sig = inspect.signature(attr)
        except (TypeError, ValueError):
            return True
        actual_params = [p for p in sig.parameters if p not in ("self", "cls")]
        if actual_params != doc_params:
            return True
    return False


# ---------------------------------------------------------------------------
# llm-judge dispatch (R-VERIFY-003)
# ---------------------------------------------------------------------------

def _normalize_bool_result(raw: Any) -> str:
    if isinstance(raw, bool):
        return "pass" if raw else "fail"
    if isinstance(raw, str):
        low = raw.strip().lower()
        if low in ("pass", "true", "passed"):
            return "pass"
        if low in ("fail", "false", "failed"):
            return "fail"
    return "pass" if raw else "fail"


def _interpret_judge_outcome(outcome: Any):
    raw = _get(outcome, "result")
    if raw is None:
        raw = _get(outcome, "verdict")
    if raw is None and not isinstance(outcome, dict):
        raw = outcome
    rationale = _get(outcome, "rationale")
    return _normalize_bool_result(raw), rationale


def _evaluate_llm_judge(component_id: str, repo_root: Path, spec: dict, judge) -> dict:
    cid = spec["id"]
    covers = spec["covers"]
    entry = {"id": cid, "covers": covers, "kind": "llm-judge"}
    if judge is None:
        entry["result"] = "skipped"
        entry["rationale"] = None
        return entry
    spec_bundle_assembler = _load_dependency(repo_root, "gen/spec-bundle-assembler", "spec_bundle_assembler")
    bundle = spec_bundle_assembler.assemble_criterion(component_id, cid, Path(repo_root))
    outcome = judge(bundle)
    result, rationale = _interpret_judge_outcome(outcome)
    entry["result"] = result
    entry["rationale"] = rationale
    return entry


# ---------------------------------------------------------------------------
# pytest execution, with a wall-clock timeout that kills the process tree
# (R-VERIFY-014)
# ---------------------------------------------------------------------------

def _run_pytest_junit(files: list, cwd: Path, pythonpath: Path, timeout: float):
    with tempfile.TemporaryDirectory() as td:
        junit_path = Path(td) / "result.xml"
        args = [
            sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
            f"--junit-xml={junit_path}",
        ] + [str(f) for f in files]
        env = dict(os.environ)
        env["PYTHONPATH"] = str(pythonpath)

        timed_out = False
        proc = subprocess.Popen(
            args, cwd=str(cwd), env=env,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            start_new_session=True,
        )
        try:
            proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass
            try:
                proc.communicate(timeout=5)
            except Exception:
                pass

        results = {}
        if junit_path.exists():
            try:
                tree = ET.parse(junit_path)
                for tc in tree.iter("testcase"):
                    name = tc.get("name")
                    failure = tc.find("failure")
                    error = tc.find("error")
                    if failure is not None:
                        results[name] = {"passed": False, "text": failure.text or failure.get("message") or ""}
                    elif error is not None:
                        results[name] = {"passed": False, "text": error.text or error.get("message") or ""}
                    else:
                        results[name] = {"passed": True, "text": None}
            except ET.ParseError:
                pass
        return results, timed_out


def _try_literal_eval(value: str):
    value = value.strip()
    try:
        return ast.literal_eval(value)
    except (ValueError, SyntaxError):
        return None


def _parse_failure(text: str):
    lines = [l.strip() for l in (text or "").splitlines() if l.strip()]
    message = lines[-1] if lines else "test failed"
    expected = actual = None
    for line in reversed(lines):
        m = _ASSERT_LINE_RE.search(line)
        if m:
            left, _op, right = m.groups()
            actual = _try_literal_eval(left)
            expected = _try_literal_eval(right)
            message = line
            break
    return message, expected, actual


def _run_single_criterion_test(file_path: Path, cwd: Path, pythonpath: Path):
    results, timed_out = _run_pytest_junit([file_path], cwd=cwd, pythonpath=pythonpath, timeout=DEFAULT_TEST_TIMEOUT)
    if timed_out:
        return False, "test run timed out", None, None
    if not results:
        return False, "no test results produced", None, None
    failing = [r for r in results.values() if not r["passed"]]
    if not failing:
        return True, None, None, None
    message, expected, actual = _parse_failure(failing[0]["text"] or "")
    return False, message, expected, actual


# ---------------------------------------------------------------------------
# Mutation testing (R-VERIFY-006) -- exactly four operators, one mutant per
# site, union-killed across all of a component's generated-test test files.
# ---------------------------------------------------------------------------

def _enumerate_sites(tree) -> list:
    sites = []
    idx = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare):
            for i, op in enumerate(node.ops):
                if type(op) in _COMPARISON_SWAPS:
                    sites.append((idx, "compare", i))
        elif isinstance(node, ast.BoolOp) and type(node.op) in _BOOLOP_SWAPS:
            sites.append((idx, "boolop", None))
        elif isinstance(node, ast.BinOp) and type(node.op) in _ARITH_SWAPS:
            sites.append((idx, "binop", None))
        elif isinstance(node, ast.Constant) and isinstance(node.value, bool):
            sites.append((idx, "boolconst", None))
        idx += 1
    return sites


def _apply_mutation(tree, site) -> None:
    walk_idx, kind, extra = site
    idx = 0
    for node in ast.walk(tree):
        if idx == walk_idx:
            if kind == "compare":
                op = node.ops[extra]
                node.ops[extra] = _COMPARISON_SWAPS[type(op)]()
            elif kind == "boolop":
                node.op = _BOOLOP_SWAPS[type(node.op)]()
            elif kind == "binop":
                node.op = _ARITH_SWAPS[type(node.op)]()
            elif kind == "boolconst":
                node.value = not node.value
            return
        idx += 1


def _run_mutation_testing(gen_dir: Path, test_files: list) -> float | None:
    py_files = [p for p in gen_dir.rglob("*.py") if "__pycache__" not in p.parts]
    if not py_files:
        return None

    file_sites = {}
    for p in py_files:
        try:
            source = p.read_text(encoding="utf-8")
            tree = ast.parse(source)
        except (SyntaxError, OSError):
            continue
        sites = _enumerate_sites(tree)
        if sites:
            file_sites[p] = (tree, sites)

    total_sites = sum(len(v[1]) for v in file_sites.values())
    if total_sites == 0:
        return 1.0

    start = time.monotonic()
    _baseline_results, baseline_timed_out = _run_pytest_junit(
        test_files, cwd=gen_dir, pythonpath=gen_dir, timeout=DEFAULT_TEST_TIMEOUT,
    )
    baseline_elapsed = time.monotonic() - start
    timeout = DEFAULT_TEST_TIMEOUT if baseline_timed_out else max(DEFAULT_TEST_TIMEOUT, baseline_elapsed * 10)

    killed = 0
    for p, (tree, sites) in file_sites.items():
        rel = p.relative_to(gen_dir)
        for site in sites:
            with tempfile.TemporaryDirectory() as sandbox:
                sandbox_dir = Path(sandbox)
                shutil.copytree(
                    gen_dir, sandbox_dir, dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("__pycache__"),
                )
                mutant_tree = copy.deepcopy(tree)
                _apply_mutation(mutant_tree, site)
                ast.fix_missing_locations(mutant_tree)
                try:
                    mutated_source = ast.unparse(mutant_tree)
                except Exception:
                    continue
                (sandbox_dir / rel).write_text(mutated_source, encoding="utf-8")
                results, timed_out = _run_pytest_junit(
                    test_files, cwd=sandbox_dir, pythonpath=sandbox_dir, timeout=timeout,
                )
                if timed_out or any(not r["passed"] for r in results.values()):
                    killed += 1
    return killed / total_sites


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------

def _compute_requirement_results(criteria_out: list) -> dict:
    req = {}
    for c in criteria_out:
        rid = c.get("covers")
        if not rid:
            continue
        passed = c.get("result") == "pass"
        req[rid] = passed if rid not in req else (req[rid] and passed)
    return {rid: ("pass" if ok else "fail") for rid, ok in req.items()}


def _compute_overall(criteria_out: list, interface_drift: bool, mutation_score, mutation_applicable: bool) -> str:
    for c in criteria_out:
        kind = c["kind"]
        result = c["result"]
        if kind in ("compiled", "generated-test") and result == "fail":
            return "fail"
        if kind == "llm-judge" and result == "fail":
            return "fail"
    if interface_drift:
        return "fail"
    if mutation_applicable and mutation_score is not None and mutation_score < MUTATION_THRESHOLD:
        return "fail"
    return "pass"


@dataclass
class VerificationReport:
    component_id: str
    criteria: list = field(default_factory=list)
    requirement_results: dict = field(default_factory=dict)
    interface_drift: bool = False
    mutation_score: Any = None
    overall: str = "fail"

    def to_dict(self) -> dict:
        return {
            "component_id": self.component_id,
            "criteria": self.criteria,
            "requirement_results": self.requirement_results,
            "interface_drift": self.interface_drift,
            "mutation_score": self.mutation_score,
            "overall": self.overall,
        }


# ---------------------------------------------------------------------------
# Non-sealed verification
# ---------------------------------------------------------------------------

def _verify_generated_component(component_id: str, repo_root: Path, slug: str, criteria_specs: list, judge, test_author) -> VerificationReport:
    gen_dir = repo_root / "gen" / slug
    module_name = _module_name_from_slug(slug)

    compiled_specs = [c for c in criteria_specs if c["kind"] == "compiled"]

    outputs_by_id = {}
    if compiled_specs:
        criterion_compiler = _load_dependency(repo_root, "pipeline/criterion-compiler", "criterion_compiler")
        compile_report = criterion_compiler.compile(
            component_id, repo_root, target="pytest",
            out_dir=repo_root / "verification" / slug / "compiled",
        )
        for o in _get(compile_report, "outputs", []):
            outputs_by_id[_get(o, "criterion_id")] = o

    gen_test_dir = repo_root / "verification" / slug / "generated-test"
    test_files_for_mutation = []
    criteria_out = []

    for spec in criteria_specs:
        cid = spec["id"]
        covers = spec["covers"]
        kind = spec["kind"]

        if kind == "compiled":
            entry = {"id": cid, "covers": covers, "kind": "compiled"}
            out = outputs_by_id.get(cid)
            if out is None:
                entry["result"] = "fail"
                entry["failure_detail"] = {
                    "message": "criterion-compiler produced no output for this criterion",
                    "expected": None, "actual": None,
                }
            elif _get(out, "status") == "error":
                entry["result"] = "fail"
                entry["failure_detail"] = {
                    "message": _get(out, "message", "compile error"),
                    "expected": None, "actual": None,
                }
            else:
                file_path = Path(_get(out, "file"))
                if not file_path.is_absolute():
                    file_path = repo_root / file_path
                passed, message, expected, actual = _run_single_criterion_test(file_path, cwd=gen_dir, pythonpath=gen_dir)
                entry["result"] = "pass" if passed else "fail"
                if not passed:
                    entry["failure_detail"] = {"message": message, "expected": expected, "actual": actual}
            criteria_out.append(entry)
            continue

        if kind == "generated-test":
            entry = {"id": cid, "covers": covers, "kind": "generated-test"}
            cache_filename = "test_" + cid.lower().replace("-", "_") + ".py"
            cache_path = gen_test_dir / cache_filename
            test_authoring = None

            if cache_path.is_file():
                file_path = cache_path
            elif test_author is not None:
                spec_bundle_assembler = _load_dependency(repo_root, "gen/spec-bundle-assembler", "spec_bundle_assembler")
                bundle = spec_bundle_assembler.assemble_criterion(component_id, cid, repo_root)
                outcome = test_author(bundle)
                model_call_error = _get(outcome, "model_call_error")
                if model_call_error:
                    msg = _get(model_call_error, "message") if not isinstance(model_call_error, str) else model_call_error
                    entry["result"] = "fail"
                    entry["failure_detail"] = {"message": msg or str(model_call_error), "expected": None, "actual": None}
                    criteria_out.append(entry)
                    continue
                file_info = _get(outcome, "file")
                if not file_info:
                    entry["result"] = "fail"
                    entry["failure_detail"] = {"message": "test_author returned no file", "expected": None, "actual": None}
                    criteria_out.append(entry)
                    continue
                content = _get(file_info, "content")
                gen_test_dir.mkdir(parents=True, exist_ok=True)
                cache_path.write_text(content, encoding="utf-8")
                file_path = cache_path
                test_authoring = {
                    "model": _get(outcome, "model"),
                    "seed": _get(outcome, "seed"),
                    "prompt_version": _get(outcome, "prompt_version"),
                    "cache_hit": _get(outcome, "cache_hit"),
                }
            else:
                entry["result"] = "fail"
                entry["failure_detail"] = {
                    "message": "no cached test and no test_author configured",
                    "expected": None, "actual": None,
                }
                criteria_out.append(entry)
                continue

            passed, message, expected, actual = _run_single_criterion_test(file_path, cwd=gen_dir, pythonpath=gen_dir)
            entry["result"] = "pass" if passed else "fail"
            if not passed:
                entry["failure_detail"] = {"message": message, "expected": expected, "actual": actual}
            if test_authoring is not None:
                entry["test_authoring"] = test_authoring
            test_files_for_mutation.append(file_path)
            criteria_out.append(entry)
            continue

        if kind == "llm-judge":
            criteria_out.append(_evaluate_llm_judge(component_id, repo_root, spec, judge))
            continue

    interface_drift = True
    try:
        module = _load_module(repo_root, gen_dir, module_name)
        interface_drift = _check_interface_drift(repo_root, slug, module)
    except Exception:
        interface_drift = True

    mutation_score = None
    if test_files_for_mutation:
        mutation_score = _run_mutation_testing(gen_dir, test_files_for_mutation)

    requirement_results = _compute_requirement_results(criteria_out)
    overall = _compute_overall(criteria_out, interface_drift, mutation_score, bool(test_files_for_mutation))

    return VerificationReport(
        component_id=component_id,
        criteria=criteria_out,
        requirement_results=requirement_results,
        interface_drift=interface_drift,
        mutation_score=mutation_score,
        overall=overall,
    )


# ---------------------------------------------------------------------------
# Sealed-component verification (R-VERIFY-017)
# ---------------------------------------------------------------------------

def _verify_sealed(component_id: str, repo_root: Path, source_path: str, criteria_specs: list, judge) -> VerificationReport:
    slug = _slug(component_id)
    code_dir = Path(repo_root) / source_path
    module_name = _module_name_from_slug(slug)
    verification_dir = Path(repo_root) / "verification" / slug
    code_dir_exists = code_dir.is_dir()

    char_test_files = []
    if verification_dir.is_dir():
        char_test_files = sorted(p for p in verification_dir.glob("test_*.py") if p.is_file())

    char_results = {}
    if code_dir_exists and char_test_files:
        char_results, _timed_out = _run_pytest_junit(
            char_test_files, cwd=code_dir, pythonpath=code_dir, timeout=DEFAULT_TEST_TIMEOUT,
        )

    criteria_out = []
    for spec in criteria_specs:
        cid = spec["id"]
        covers = spec["covers"]
        kind = spec["kind"]

        if kind in ("compiled", "generated-test"):
            entry = {"id": cid, "covers": covers, "kind": kind}
            if not code_dir_exists:
                entry["result"] = "fail"
                entry["failure_detail"] = {
                    "message": f"source_path {source_path} does not exist",
                    "expected": None, "actual": None,
                }
            else:
                test_prefix = "test_" + cid.lower().replace("-", "_")
                matches = [n for n in char_results if n == test_prefix or n.startswith(test_prefix + "_")]
                if not matches:
                    entry["result"] = "fail"
                    entry["failure_detail"] = {"message": "no characterization test", "expected": None, "actual": None}
                else:
                    failing = [n for n in matches if not char_results[n]["passed"]]
                    if not failing:
                        entry["result"] = "pass"
                    else:
                        entry["result"] = "fail"
                        message, expected, actual = _parse_failure(char_results[failing[0]]["text"] or "")
                        entry["failure_detail"] = {"message": message, "expected": expected, "actual": actual}
            criteria_out.append(entry)
            continue

        if kind == "llm-judge":
            criteria_out.append(_evaluate_llm_judge(component_id, repo_root, spec, judge))
            continue

    interface_drift = True
    if code_dir_exists:
        try:
            module = _load_module(repo_root, code_dir, module_name)
            interface_drift = _check_interface_drift(repo_root, slug, module)
        except Exception:
            interface_drift = True

    requirement_results = _compute_requirement_results(criteria_out)
    overall = _compute_overall(criteria_out, interface_drift, mutation_score=None, mutation_applicable=False)

    return VerificationReport(
        component_id=component_id,
        criteria=criteria_out,
        requirement_results=requirement_results,
        interface_drift=interface_drift,
        mutation_score=None,
        overall=overall,
    )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def verify(component_id: str, repo_root: Path, judge=None, test_author=None) -> VerificationReport:
    repo_root = Path(repo_root)
    slug = _slug(component_id)
    component_md = repo_root / "specs" / "components" / slug / "component.md"
    frontmatter = _read_frontmatter(component_md)
    sealed = frontmatter.get("sealed", "").strip().lower() == "true"
    source_path = frontmatter.get("source_path")
    acceptance_dir = repo_root / "specs" / "components" / slug / "acceptance"
    criteria_specs = _parse_acceptance_criteria(acceptance_dir)

    if sealed and source_path:
        return _verify_sealed(component_id, repo_root, source_path, criteria_specs, judge)

    return _verify_generated_component(component_id, repo_root, slug, criteria_specs, judge, test_author)


_USAGE = "usage: hotdocs verify-component <component-id> [--repo-root=<dir>] [--format=json|text]"


def main(argv: list | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    argv = list(argv)

    repo_root = Path.cwd()
    fmt = "text"
    positional = []

    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg.startswith("--repo-root"):
            if "=" in arg:
                repo_root = Path(arg.split("=", 1)[1])
            else:
                if i + 1 >= len(argv):
                    print(_USAGE, file=sys.stderr)
                    return 2
                i += 1
                repo_root = Path(argv[i])
        elif arg.startswith("--format"):
            if "=" in arg:
                fmt = arg.split("=", 1)[1]
            else:
                if i + 1 >= len(argv):
                    print(_USAGE, file=sys.stderr)
                    return 2
                i += 1
                fmt = argv[i]
        elif arg.startswith("--"):
            print(_USAGE, file=sys.stderr)
            return 2
        else:
            positional.append(arg)
        i += 1

    if not positional or len(positional) > 1:
        print(_USAGE, file=sys.stderr)
        return 2

    component_id = positional[0]

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
        print(f"{report.component_id}: {report.overall}")
        for c in report.criteria:
            print(f"  {c['id']}: {c['result']}")

    return 0 if report.overall == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())