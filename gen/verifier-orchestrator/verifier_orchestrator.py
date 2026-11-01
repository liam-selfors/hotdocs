import argparse
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
from dataclasses import dataclass
from pathlib import Path

GATE_VERSION = "verifier-orchestrator@2.0.0"

MUTATION_SCORE_THRESHOLD = 0.8
BASELINE_TIMEOUT_FLOOR = 10.0

_HEADING_RE = re.compile(r'^#\s*(AC-[\w-]+)', re.MULTILINE)
_COVERS_RE = re.compile(r'Covers:\s*\**\s*(.+)', re.IGNORECASE)
_KIND_RE = re.compile(r'Kind:\s*\**\s*`?(compiled|generated-test|llm-judge)`?', re.IGNORECASE)
_RID_RE = re.compile(r'R-[A-Za-z0-9][\w-]*')
_SIG_RE = re.compile(r'^([A-Za-z_][A-Za-z0-9_]*)\(([^)]*)\)(?:\s*->\s*.+)?\s*$')

_MODULE_CACHE = {}


@dataclass
class VerificationReport:
    component_id: str
    criteria: list
    requirement_results: dict
    interface_drift: bool
    mutation_score: float
    overall: str

    def to_dict(self):
        return {
            "component_id": self.component_id,
            "criteria": self.criteria,
            "requirement_results": self.requirement_results,
            "interface_drift": self.interface_drift,
            "mutation_score": self.mutation_score,
            "overall": self.overall,
        }

    def __getitem__(self, key):
        return self.to_dict()[key]

    def get(self, key, default=None):
        return self.to_dict().get(key, default)


def _get(obj, key, default=None):
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _slug(component_id):
    return component_id[len("comp-"):] if component_id.startswith("comp-") else component_id


# A module cached under its own module_name must still be keyed by repo_root too,
# since two different repos may use the same component slug in the same process.
def _load_module(repo_root, module_dir, module_name):
    key = (str(Path(repo_root).resolve()), module_name)
    cached = _MODULE_CACHE.get(key)
    if cached is not None:
        return cached
    module_dir = Path(module_dir)
    flat_file = module_dir / f"{module_name}.py"
    pkg_init = module_dir / module_name / "__init__.py"
    if flat_file.is_file():
        spec = importlib.util.spec_from_file_location(module_name, flat_file)
    elif pkg_init.is_file():
        spec = importlib.util.spec_from_file_location(
            module_name, pkg_init, submodule_search_locations=[str(module_dir / module_name)]
        )
    else:
        raise FileNotFoundError(f"module '{module_name}' not found under {module_dir}")
    module = importlib.util.module_from_spec(spec)
    # Must register before exec_module: dataclasses defined in the loaded module
    # resolve sys.modules[cls.__module__] while their class body executes.
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    _MODULE_CACHE[key] = module
    return module


def _load_component_module(repo_root, slug):
    module_name = slug.replace("-", "_")
    module_dir = Path(repo_root) / "gen" / slug
    return _load_module(repo_root, module_dir, module_name)


def _load_criterion_compiler(repo_root):
    module_dir = Path(repo_root) / "pipeline" / "criterion-compiler"
    return _load_module(repo_root, module_dir, "criterion_compiler")


def _load_spec_bundle_assembler(repo_root):
    module_dir = Path(repo_root) / "gen" / "spec-bundle-assembler"
    return _load_module(repo_root, module_dir, "spec_bundle_assembler")


def _parse_criterion_file(path):
    text = path.read_text()
    m = _HEADING_RE.search(text)
    if not m:
        raise ValueError(f"{path}: no '# AC-...' heading found")
    criterion_id = m.group(1)
    cm = _COVERS_RE.search(text)
    if not cm:
        raise ValueError(f"{path}: no 'Covers:' field found")
    covers_raw = cm.group(1).strip().strip("`*").strip()
    km = _KIND_RE.search(text)
    if not km:
        raise ValueError(f"{path}: no 'Kind:' field found")
    kind = km.group(1).strip().lower()
    return {"id": criterion_id, "covers": covers_raw, "kind": kind, "file": str(path)}


def _load_criteria(repo_root, slug):
    acc_dir = Path(repo_root) / "specs" / "components" / slug / "acceptance"
    files = sorted(acc_dir.glob("*.md"))
    return [_parse_criterion_file(f) for f in files]


def _run_pytest(test_path, cwd, pythonpath, timeout):
    env = os.environ.copy()
    env["PYTHONPATH"] = str(pythonpath)
    start = time.monotonic()
    proc = subprocess.Popen(
        [sys.executable, "-m", "pytest", str(test_path), "-q", "--no-header", "-p", "no:cacheprovider"],
        cwd=str(cwd),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    try:
        stdout, stderr = proc.communicate(timeout=timeout)
        duration = time.monotonic() - start
        return {
            "passed": proc.returncode == 0,
            "output": (stdout or "") + (stderr or ""),
            "duration": duration,
            "timed_out": False,
        }
    except subprocess.TimeoutExpired:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except (ProcessLookupError, PermissionError, AttributeError, OSError):
            proc.kill()
        try:
            proc.communicate(timeout=5)
        except Exception:
            pass
        return {"passed": False, "output": "", "duration": timeout, "timed_out": True}


def _try_literal(text):
    try:
        return ast.literal_eval(text.strip())
    except Exception:
        return None


def _parse_pytest_failure(output, timed_out, timeout):
    if timed_out:
        return {"message": f"test run timed out after {timeout:.1f}s", "expected": None, "actual": None}
    e_lines = [ln.strip() for ln in output.splitlines() if re.match(r'^E\s', ln.strip())]
    assert_line = next((ln for ln in e_lines if "assert" in ln), None)
    chosen = assert_line or (e_lines[0] if e_lines else None)
    message = "test failed"
    expected = actual = None
    if chosen:
        content = re.sub(r'^E\s+', '', chosen).strip()
        message = content
        m = re.match(r'assert\s+(.+?)\s*(==|!=)\s*(.+)$', content)
        if m:
            left_raw, _op, right_raw = m.groups()
            actual = _try_literal(left_raw)
            expected = _try_literal(right_raw)
    else:
        tail = [ln for ln in output.splitlines() if ln.strip()]
        if tail:
            message = tail[-1].strip()
    return {"message": message, "expected": expected, "actual": actual}


def _compile_criteria(repo_root, component_id):
    criterion_compiler = _load_criterion_compiler(repo_root)
    report = criterion_compiler.compile(component_id, repo_root)
    outputs = _get(report, "outputs", []) or []
    result = {}
    for o in outputs:
        cid = _get(o, "criterion_id")
        if cid is not None:
            result[cid] = o
    return result


def _run_compiled_criterion(c, compile_outputs, gen_dir, repo_root, timeout):
    entry = {"id": c["id"], "covers": c["covers"], "kind": "compiled"}
    out = compile_outputs.get(c["id"])
    if out is None:
        entry["result"] = "fail"
        entry["failure_detail"] = {
            "message": f"criterion-compiler produced no output for {c['id']}",
            "expected": None,
            "actual": None,
        }
        return entry, None
    status = _get(out, "status")
    if status != "compiled":
        entry["result"] = "fail"
        entry["failure_detail"] = {
            "message": _get(out, "message") or f"compilation failed for {c['id']}",
            "expected": None,
            "actual": None,
        }
        return entry, None
    file_rel = _get(out, "file")
    test_path = Path(repo_root) / file_rel
    run = _run_pytest(test_path, cwd=gen_dir, pythonpath=gen_dir, timeout=timeout)
    if run["passed"]:
        entry["result"] = "pass"
        return entry, run["duration"]
    entry["result"] = "fail"
    entry["failure_detail"] = _parse_pytest_failure(run["output"], run["timed_out"], timeout)
    return entry, run["duration"]


def _run_generated_test_criterion(c, component_id, slug, repo_root, gen_dir, test_author, timeout):
    criterion_id = c["id"]
    entry = {"id": criterion_id, "covers": c["covers"], "kind": "generated-test"}
    test_dir = Path(repo_root) / "verification" / slug / "generated-test"
    filename = f"test_{criterion_id.lower().replace('-', '_')}.py"
    test_path = test_dir / filename
    test_authoring = None

    if not test_path.is_file():
        if test_author is None:
            entry["result"] = "fail"
            entry["failure_detail"] = {
                "message": "no cached test and no test_author configured",
                "expected": None,
                "actual": None,
            }
            return entry, None, None
        assembler = _load_spec_bundle_assembler(repo_root)
        bundle = assembler.assemble_criterion(component_id, criterion_id, repo_root)
        outcome = test_author(bundle)
        model_call_error = _get(outcome, "model_call_error")
        test_authoring = {
            "model": _get(outcome, "model"),
            "seed": _get(outcome, "seed"),
            "prompt_version": _get(outcome, "prompt_version"),
            "cache_hit": _get(outcome, "cache_hit"),
        }
        if model_call_error:
            entry["result"] = "fail"
            entry["failure_detail"] = {
                "message": str(model_call_error),
                "expected": None,
                "actual": None,
            }
            entry["test_authoring"] = test_authoring
            return entry, None, None
        file_info = _get(outcome, "file")
        content = _get(file_info, "content") or ""
        test_dir.mkdir(parents=True, exist_ok=True)
        test_path.write_text(content)

    run = _run_pytest(test_path, cwd=gen_dir, pythonpath=gen_dir, timeout=timeout)
    if run["passed"]:
        entry["result"] = "pass"
    else:
        entry["result"] = "fail"
        entry["failure_detail"] = _parse_pytest_failure(run["output"], run["timed_out"], timeout)
    if test_authoring is not None:
        entry["test_authoring"] = test_authoring
    return entry, test_path, run["duration"]


def _normalize_result(value):
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
    return "fail"


def _judge_outcome_to_result(outcome):
    if isinstance(outcome, (bool, str, int, float)):
        return _normalize_result(outcome), None
    result = _get(outcome, "result")
    if result is None:
        result = _get(outcome, "verdict")
    rationale = _get(outcome, "rationale")
    return _normalize_result(result), rationale


def _run_llm_judge_criterion(c, component_id, repo_root, judge):
    criterion_id = c["id"]
    entry = {"id": criterion_id, "covers": c["covers"], "kind": "llm-judge"}
    if judge is None:
        entry["result"] = "skipped"
        entry["rationale"] = None
        return entry
    assembler = _load_spec_bundle_assembler(repo_root)
    bundle = assembler.assemble_criterion(component_id, criterion_id, repo_root)
    outcome = judge(bundle)
    result, rationale = _judge_outcome_to_result(outcome)
    entry["result"] = result
    entry["rationale"] = rationale
    return entry


def _project_requirement_results(criteria_entries):
    by_req = {}
    for entry in criteria_entries:
        rids = _RID_RE.findall(entry.get("covers") or "")
        result = entry.get("result")
        for rid in rids:
            by_req.setdefault(rid, []).append(result)
    return {
        rid: ("pass" if all(r == "pass" for r in results) else "fail")
        for rid, results in by_req.items()
    }


def _split_params(params_str):
    parts = []
    depth = 0
    current = ""
    for ch in params_str:
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
    return [p.strip() for p in parts if p.strip()]


def _param_base_name(param):
    p = param.strip().lstrip("*")
    name = re.split(r'[:=]', p, 1)[0].strip()
    return name


def _extract_documented_callables(markdown_text):
    callables = {}
    in_code = False
    for line in markdown_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            in_code = not in_code
            continue
        if not in_code:
            continue
        m = _SIG_RE.match(stripped)
        if m:
            name, params_str = m.group(1), m.group(2)
            params = [_param_base_name(p) for p in _split_params(params_str)]
            params = [p for p in params if p]
            callables[name] = params
    return callables


def _check_interface_drift(repo_root, slug, component_module):
    iface_dir = Path(repo_root) / "specs" / "components" / slug / "interface"
    documented = {}
    for fname in ("library.md", "cli.md"):
        fpath = iface_dir / fname
        if fpath.is_file():
            documented.update(_extract_documented_callables(fpath.read_text()))
    for name, params in documented.items():
        target = getattr(component_module, name, None)
        if target is None or not callable(target):
            return True
        try:
            sig = inspect.signature(target)
        except (TypeError, ValueError):
            return True
        real_params = list(sig.parameters.keys())
        if real_params != params:
            return True
    return False


_CMP_SWAP = {
    ast.Eq: ast.NotEq, ast.NotEq: ast.Eq,
    ast.Lt: ast.GtE, ast.GtE: ast.Lt,
    ast.Gt: ast.LtE, ast.LtE: ast.Gt,
    ast.Is: ast.IsNot, ast.IsNot: ast.Is,
    ast.In: ast.NotIn, ast.NotIn: ast.In,
}
_BOOL_SWAP = {ast.And: ast.Or, ast.Or: ast.And}
_ARITH_SWAP = {
    ast.Add: ast.Sub, ast.Sub: ast.Add,
    ast.Mult: ast.Div, ast.Div: ast.Mult,
    ast.FloorDiv: ast.Mod, ast.Mod: ast.FloorDiv,
}


class _MutationTransformer(ast.NodeTransformer):
    def __init__(self, target_index):
        self.target_index = target_index
        self.index = 0
        self.applied = False

    def _consume(self, node, build):
        current = self.index
        self.index += 1
        if current == self.target_index:
            self.applied = True
            return build()
        return node

    def visit_Compare(self, node):
        self.generic_visit(node)
        if len(node.ops) == 1 and type(node.ops[0]) in _CMP_SWAP:
            op_cls = _CMP_SWAP[type(node.ops[0])]

            def build():
                node.ops = [op_cls()]
                return node

            return self._consume(node, build)
        return node

    def visit_BoolOp(self, node):
        self.generic_visit(node)
        if type(node.op) in _BOOL_SWAP:
            op_cls = _BOOL_SWAP[type(node.op)]

            def build():
                node.op = op_cls()
                return node

            return self._consume(node, build)
        return node

    def visit_BinOp(self, node):
        self.generic_visit(node)
        if type(node.op) in _ARITH_SWAP:
            op_cls = _ARITH_SWAP[type(node.op)]

            def build():
                node.op = op_cls()
                return node

            return self._consume(node, build)
        return node

    def visit_Constant(self, node):
        if isinstance(node.value, bool):
            def build():
                node.value = not node.value
                return node

            return self._consume(node, build)
        return node


def _count_mutation_sites(tree):
    counter = _MutationTransformer(-1)
    counter.visit(tree)
    return counter.index


def _mutant_is_killed(gen_dir, rel, idx, generated_test_files, timeout):
    target_file = Path(gen_dir) / rel
    source = target_file.read_text()
    tree = ast.parse(source)
    transformer = _MutationTransformer(idx)
    mutated_tree = transformer.visit(tree)
    if not transformer.applied:
        return False
    ast.fix_missing_locations(mutated_tree)
    mutated_source = ast.unparse(mutated_tree)
    with tempfile.TemporaryDirectory() as tmp:
        sandbox = Path(tmp) / "sandbox"
        shutil.copytree(gen_dir, sandbox)
        (sandbox / rel).write_text(mutated_source)
        for test_file in generated_test_files:
            sandbox_test = sandbox / test_file.name
            sandbox_test.write_text(test_file.read_text())
            run = _run_pytest(sandbox_test, cwd=sandbox, pythonpath=sandbox, timeout=timeout)
            sandbox_test.unlink()
            if not run["passed"]:
                return True
    return False


def _compute_mutation_score(gen_dir, generated_test_files, baseline_duration):
    if not generated_test_files:
        return 1.0
    py_files = sorted(p for p in Path(gen_dir).rglob("*.py") if p.is_file())
    sites = []
    for py_file in py_files:
        try:
            tree = ast.parse(py_file.read_text())
        except SyntaxError:
            continue
        rel = py_file.relative_to(gen_dir)
        for i in range(_count_mutation_sites(tree)):
            sites.append((rel, i))
    if not sites:
        return 1.0
    timeout = max(BASELINE_TIMEOUT_FLOOR, 10.0 * baseline_duration)
    killed = 0
    for rel, idx in sites:
        if _mutant_is_killed(gen_dir, rel, idx, generated_test_files, timeout):
            killed += 1
    return killed / len(sites)


def _compute_overall(criteria_entries, interface_drift, mutation_score, has_generated_test):
    if interface_drift:
        return "fail"
    for entry in criteria_entries:
        if entry["kind"] in ("compiled", "generated-test") and entry["result"] == "fail":
            return "fail"
        if entry["kind"] == "llm-judge" and entry["result"] == "fail":
            return "fail"
    if has_generated_test and mutation_score < MUTATION_SCORE_THRESHOLD:
        return "fail"
    return "pass"


def verify(component_id, repo_root, judge=None, test_author=None):
    repo_root = Path(repo_root)
    slug = _slug(component_id)
    criteria_specs = _load_criteria(repo_root, slug)
    gen_dir = repo_root / "gen" / slug

    compiled_specs = [c for c in criteria_specs if c["kind"] == "compiled"]
    compile_outputs = _compile_criteria(repo_root, component_id) if compiled_specs else {}

    criteria_entries = []
    generated_test_files = []
    generated_test_durations = []

    for c in criteria_specs:
        kind = c["kind"]
        if kind == "compiled":
            entry, _duration = _run_compiled_criterion(
                c, compile_outputs, gen_dir, repo_root, timeout=BASELINE_TIMEOUT_FLOOR
            )
            criteria_entries.append(entry)
        elif kind == "generated-test":
            entry, test_path, duration = _run_generated_test_criterion(
                c, component_id, slug, repo_root, gen_dir, test_author, timeout=BASELINE_TIMEOUT_FLOOR
            )
            criteria_entries.append(entry)
            if test_path is not None:
                generated_test_files.append(test_path)
                if duration is not None:
                    generated_test_durations.append(duration)
        elif kind == "llm-judge":
            entry = _run_llm_judge_criterion(c, component_id, repo_root, judge)
            criteria_entries.append(entry)
        else:
            raise ValueError(f"{c['id']}: unknown criterion kind '{kind}'")

    try:
        component_module = _load_component_module(repo_root, slug)
        interface_drift = _check_interface_drift(repo_root, slug, component_module)
    except Exception:
        interface_drift = True

    baseline_duration = sum(generated_test_durations) if generated_test_durations else 0.0
    mutation_score = _compute_mutation_score(gen_dir, generated_test_files, baseline_duration)

    requirement_results = _project_requirement_results(criteria_entries)
    overall = _compute_overall(
        criteria_entries, interface_drift, mutation_score, bool(generated_test_files)
    )

    return VerificationReport(
        component_id=component_id,
        criteria=criteria_entries,
        requirement_results=requirement_results,
        interface_drift=interface_drift,
        mutation_score=mutation_score,
        overall=overall,
    )


def main(argv=None):
    parser = argparse.ArgumentParser(prog="hotdocs verify")
    parser.add_argument("component_id")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--format", choices=["json", "text"], default="text")
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        code = exc.code
        return code if isinstance(code, int) else 2

    try:
        report = verify(args.component_id, Path(args.repo_root))
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    report_dict = report.to_dict()

    if args.format == "json":
        print(json.dumps(report_dict, indent=2))
    else:
        print(f"{report_dict['component_id']}: {report_dict['overall']}")
        for c in report_dict["criteria"]:
            print(f"  {_get(c, 'id')}: {_get(c, 'result')}")

    return 0 if report_dict["overall"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())