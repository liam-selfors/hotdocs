from __future__ import annotations

import argparse
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
from dataclasses import dataclass, field
from pathlib import Path


MUTATION_SCORE_BAR = 0.8


@dataclass
class VerificationReport:
    component_id: str
    criteria: list = field(default_factory=list)
    requirement_results: dict = field(default_factory=dict)
    interface_drift: bool = False
    mutation_score: float = 1.0
    overall: str = "fail"


_MODULE_CACHE: dict = {}


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _slug(component_id: str) -> str:
    return component_id[len("comp-"):] if component_id.startswith("comp-") else component_id


def _read_text(path: Path) -> str:
    try:
        return path.read_text()
    except OSError:
        return ""


def _load_module(repo_root: Path, module_dir: Path, module_name: str):
    key = (str(repo_root), module_name)
    if key in _MODULE_CACHE:
        return _MODULE_CACHE[key]
    pkg_init = module_dir / module_name / "__init__.py"
    if pkg_init.exists():
        file_path = pkg_init
        search_locations = [str(module_dir / module_name)]
    else:
        file_path = module_dir / f"{module_name}.py"
        search_locations = None
    spec = importlib.util.spec_from_file_location(
        module_name, file_path, submodule_search_locations=search_locations
    )
    module = importlib.util.module_from_spec(spec)
    # Must be registered before exec_module: dataclasses defined in the
    # loaded module resolve sys.modules[cls.__module__] at class-body time.
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    _MODULE_CACHE[key] = module
    return module


def _load_criterion_compiler(repo_root: Path):
    return _load_module(repo_root, repo_root / "pipeline" / "criterion-compiler", "criterion_compiler")


def _load_spec_bundle_assembler(repo_root: Path):
    return _load_module(repo_root, repo_root / "gen" / "spec-bundle-assembler", "spec_bundle_assembler")


_ID_RE = re.compile(r"\b(AC-[A-Za-z0-9]+-\d+)\b")
_COVERS_RE = re.compile(r"(?i)covers\s*:\s*(R-[\w-]+)")
_KIND_RE = re.compile(r"(?i)kind\s*:\s*(compiled|generated-test|llm-judge)")


def _parse_acceptance_file(path: Path) -> dict:
    text = path.read_text()
    plain = text.replace("*", "")
    id_m = _ID_RE.search(plain) or _ID_RE.search(path.stem.upper())
    covers_m = _COVERS_RE.search(plain)
    kind_m = _KIND_RE.search(plain)
    return {
        "id": id_m.group(1) if id_m else path.stem.upper(),
        "covers": covers_m.group(1) if covers_m else "",
        "kind": kind_m.group(1).lower() if kind_m else "",
    }


def _criterion_test_filename(criterion_id: str) -> str:
    return f"test_{criterion_id.lower().replace('-', '_')}.py"


def _run_pytest(test_paths, cwd: Path, pythonpath: Path, timeout: float) -> dict:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(pythonpath)
    cmd = [sys.executable, "-m", "pytest", "-q", "--tb=short"] + [str(p) for p in test_paths]
    start = time.monotonic()
    proc = subprocess.Popen(
        cmd, cwd=str(cwd), env=env,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, start_new_session=True,
    )
    timed_out = False
    try:
        out, _ = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except ProcessLookupError:
            pass
        out, _ = proc.communicate()
    duration = time.monotonic() - start
    passed = (not timed_out) and proc.returncode == 0
    return {"passed": passed, "output": out or "", "timed_out": timed_out, "duration": duration}


def _parse_failure_detail(output: str) -> dict:
    message = ""
    expected = None
    actual = None
    for line in output.splitlines():
        s = line.strip()
        if s.startswith("E "):
            message = s[2:].strip()
            m = re.match(r"assert\s+(.+?)\s*==\s*(.+)$", message)
            if m:
                try:
                    actual = ast.literal_eval(m.group(1).strip())
                    expected = ast.literal_eval(m.group(2).strip())
                except Exception:
                    pass
            break
    if not message:
        lines = [l for l in output.splitlines() if l.strip()]
        message = lines[-1].strip() if lines else "test failed"
    return {"message": message, "expected": expected, "actual": actual}


def _process_compiled(component_id, repo_root, gen_dir, criteria_meta, verification_dir):
    compiled_ids = [c["id"] for c in criteria_meta if c["kind"] == "compiled"]
    results = {}
    if not compiled_ids:
        return results
    cc = _load_criterion_compiler(repo_root)
    report = cc.compile(component_id, repo_root, target="pytest", out_dir=verification_dir / "compiled")
    outputs = _get(report, "outputs", [])
    by_id = {}
    for out in outputs:
        by_id[_get(out, "criterion_id")] = out
    for cid in compiled_ids:
        out = by_id.get(cid)
        if out is None:
            results[cid] = {
                "result": "fail",
                "failure_detail": {
                    "message": "criterion-compiler produced no output for this criterion",
                    "expected": None, "actual": None,
                },
            }
            continue
        status = _get(out, "status")
        if status != "compiled":
            results[cid] = {
                "result": "fail",
                "failure_detail": {
                    "message": _get(out, "message") or "compile error",
                    "expected": None, "actual": None,
                },
            }
            continue
        file_rel = _get(out, "file")
        test_path = Path(file_rel)
        if not test_path.is_absolute():
            test_path = repo_root / test_path
        # Import search path scoped to gen/<component>/ itself (R-VERIFY-001):
        # a broader ancestor resolves the emitted `import <module_name>` as
        # an empty implicit namespace package instead of the real module.
        run = _run_pytest([test_path], cwd=gen_dir, pythonpath=gen_dir, timeout=10.0)
        if run["passed"]:
            results[cid] = {"result": "pass"}
        else:
            results[cid] = {"result": "fail", "failure_detail": _parse_failure_detail(run["output"])}
    return results


def _process_generated_test(component_id, repo_root, gen_dir, criteria_meta, verification_dir, test_author, sba):
    gt_meta = [c for c in criteria_meta if c["kind"] == "generated-test"]
    results = {}
    test_files = []
    gen_test_dir = verification_dir / "generated-test"
    for c in gt_meta:
        cid = c["id"]
        cache_path = gen_test_dir / _criterion_test_filename(cid)
        test_authoring_meta = None
        if cache_path.exists():
            test_path = cache_path
        elif test_author is not None:
            bundle = sba.assemble_criterion(component_id, cid, repo_root)
            outcome = test_author(bundle)
            err = _get(outcome, "model_call_error")
            if err:
                msg = _get(err, "message")
                if msg is None:
                    msg = str(err)
                results[cid] = {
                    "result": "fail",
                    "failure_detail": {"message": str(msg), "expected": None, "actual": None},
                }
                continue
            file_info = _get(outcome, "file")
            content = _get(file_info, "content")
            if content is None:
                results[cid] = {
                    "result": "fail",
                    "failure_detail": {
                        "message": "test_author produced no file content",
                        "expected": None, "actual": None,
                    },
                }
                continue
            gen_test_dir.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(content)
            test_path = cache_path
            test_authoring_meta = {
                "model": _get(outcome, "model"),
                "seed": _get(outcome, "seed"),
                "prompt_version": _get(outcome, "prompt_version"),
                "cache_hit": _get(outcome, "cache_hit"),
            }
        else:
            results[cid] = {
                "result": "fail",
                "failure_detail": {
                    "message": "no cached test and no test_author configured",
                    "expected": None, "actual": None,
                },
            }
            continue
        run = _run_pytest([test_path], cwd=gen_dir, pythonpath=gen_dir, timeout=10.0)
        entry = {"result": "pass"} if run["passed"] else {
            "result": "fail", "failure_detail": _parse_failure_detail(run["output"])
        }
        if test_authoring_meta is not None:
            entry["test_authoring"] = test_authoring_meta
        results[cid] = entry
        test_files.append(test_path)
    return results, test_files


def _normalize_judge_result(raw) -> str:
    if isinstance(raw, bool):
        return "pass" if raw else "fail"
    if isinstance(raw, str):
        r = raw.strip().lower()
        if r in ("pass", "passed", "true"):
            return "pass"
        if r in ("fail", "failed", "false"):
            return "fail"
    return "fail"


def _interpret_judge_outcome(outcome):
    if isinstance(outcome, dict):
        if "result" in outcome:
            raw = outcome.get("result")
        elif "verdict" in outcome:
            raw = outcome.get("verdict")
        else:
            raw = outcome
        rationale = outcome.get("rationale")
    elif hasattr(outcome, "result") or hasattr(outcome, "verdict"):
        raw = getattr(outcome, "result", None)
        if raw is None:
            raw = getattr(outcome, "verdict", None)
        rationale = getattr(outcome, "rationale", None)
    else:
        raw = outcome
        rationale = None
    return _normalize_judge_result(raw), rationale


def _process_llm_judge(component_id, repo_root, criteria_meta, judge, sba):
    lj_meta = [c for c in criteria_meta if c["kind"] == "llm-judge"]
    results = {}
    for c in lj_meta:
        cid = c["id"]
        if judge is None:
            results[cid] = {"result": "skipped", "rationale": None}
            continue
        bundle = sba.assemble_criterion(component_id, cid, repo_root)
        outcome = judge(bundle)
        result, rationale = _interpret_judge_outcome(outcome)
        results[cid] = {"result": result, "rationale": rationale}
    return results


_SIG_RE = re.compile(r"^([A-Za-z_]\w*)\(([^)]*)\)")


def _parse_params(params_str: str) -> list:
    tokens = []
    current = ""
    depth = 0
    for ch in params_str:
        if ch in "[(":
            depth += 1
        elif ch in "])":
            depth -= 1
        if ch == "," and depth == 0:
            tokens.append(current)
            current = ""
        else:
            current += ch
    if current.strip():
        tokens.append(current)
    params = []
    for t in tokens:
        t = t.strip()
        if not t or t in ("*", "/"):
            continue
        t = t.lstrip("*")
        name = t.split(":")[0].split("=")[0].strip()
        if name:
            params.append(name)
    return params


def _parse_library_signatures(text: str) -> dict:
    sigs = {}
    in_fence = False
    for line in text.splitlines():
        if line.strip().startswith("```"):
            in_fence = not in_fence
            continue
        if not in_fence:
            continue
        m = _SIG_RE.match(line.strip())
        if m:
            sigs[m.group(1)] = _parse_params(m.group(2))
    return sigs


def _cli_has_commands(cli_text: str) -> bool:
    in_fence = False
    for line in cli_text.splitlines():
        if line.strip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence and line.strip():
            return True
    return False


def _real_params(func) -> list:
    try:
        sig = inspect.signature(func)
    except (TypeError, ValueError):
        return None
    return [p.name for p in sig.parameters.values()]


def _check_interface_drift(module, library_text: str, cli_text: str) -> bool:
    drift = False
    for name, params in _parse_library_signatures(library_text).items():
        func = getattr(module, name, None)
        if func is None or not callable(func):
            drift = True
            continue
        real = _real_params(func)
        if real is None or real != params:
            drift = True
    if _cli_has_commands(cli_text) and not callable(getattr(module, "main", None)):
        drift = True
    return drift


_ARITH_SWAP = {ast.Add: ast.Sub, ast.Sub: ast.Add, ast.Mult: ast.Div, ast.Div: ast.Mult}
_COMPARE_SWAP = {
    ast.Eq: ast.NotEq, ast.NotEq: ast.Eq,
    ast.Lt: ast.GtE, ast.GtE: ast.Lt,
    ast.Gt: ast.LtE, ast.LtE: ast.Gt,
    ast.Is: ast.IsNot, ast.IsNot: ast.Is,
    ast.In: ast.NotIn, ast.NotIn: ast.In,
}


def _mutation_sites(tree) -> list:
    sites = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare) and any(type(op) in _COMPARE_SWAP for op in node.ops):
            sites.append(node)
        elif isinstance(node, ast.BoolOp):
            sites.append(node)
        elif isinstance(node, ast.BinOp) and type(node.op) in _ARITH_SWAP:
            sites.append(node)
        elif isinstance(node, ast.Constant) and isinstance(node.value, bool):
            sites.append(node)
    return sites


def _apply_mutation(node) -> None:
    if isinstance(node, ast.Compare):
        node.ops = [_COMPARE_SWAP.get(type(op), type(op))() for op in node.ops]
    elif isinstance(node, ast.BoolOp):
        node.op = ast.Or() if isinstance(node.op, ast.And) else ast.And()
    elif isinstance(node, ast.BinOp):
        node.op = _ARITH_SWAP[type(node.op)]()
    elif isinstance(node, ast.Constant):
        node.value = not node.value


def _module_target_files(gen_dir: Path, module_name: str) -> list:
    pkg_dir = gen_dir / module_name
    if (pkg_dir / "__init__.py").exists():
        return sorted(pkg_dir.rglob("*.py"))
    flat = gen_dir / f"{module_name}.py"
    return [flat] if flat.exists() else []


def _compute_mutation_score(gen_dir: Path, module_name: str, test_files: list, timeout: float) -> float:
    targets = _module_target_files(gen_dir, module_name)
    sites = []
    for f in targets:
        tree = ast.parse(f.read_text())
        for i in range(len(_mutation_sites(tree))):
            sites.append((f, i))
    if not sites:
        return 1.0
    killed = 0
    for f, idx in sites:
        with tempfile.TemporaryDirectory() as tmp:
            mutant_dir = Path(tmp) / "mutant"
            shutil.copytree(gen_dir, mutant_dir)
            rel = f.relative_to(gen_dir)
            target_file = mutant_dir / rel
            tree = ast.parse(f.read_text())
            _apply_mutation(_mutation_sites(tree)[idx])
            ast.fix_missing_locations(tree)
            target_file.write_text(ast.unparse(tree))
            # cwd and PYTHONPATH both point at the mutant copy, never
            # repo_root, so a test's own relative sys.path entry resolves
            # to the mutant instead of the original module (D159).
            run = _run_pytest(test_files, cwd=mutant_dir, pythonpath=mutant_dir, timeout=timeout)
            if run["timed_out"] or not run["passed"]:
                killed += 1
    return killed / len(sites)


def verify(component_id: str, repo_root: Path, judge=None, test_author=None) -> VerificationReport:
    repo_root = Path(repo_root)
    slug = _slug(component_id)
    gen_dir = repo_root / "gen" / slug
    acceptance_dir = repo_root / "specs" / "components" / slug / "acceptance"
    interface_dir = repo_root / "specs" / "components" / slug / "interface"
    verification_dir = repo_root / "verification" / slug

    criteria_meta = []
    if acceptance_dir.exists():
        for f in sorted(acceptance_dir.glob("*.md")):
            criteria_meta.append(_parse_acceptance_file(f))

    sba = _load_spec_bundle_assembler(repo_root)

    compiled_results = _process_compiled(component_id, repo_root, gen_dir, criteria_meta, verification_dir)
    gt_results, gt_test_files = _process_generated_test(
        component_id, repo_root, gen_dir, criteria_meta, verification_dir, test_author, sba
    )
    lj_results = _process_llm_judge(component_id, repo_root, criteria_meta, judge, sba)

    library_text = _read_text(interface_dir / "library.md")
    cli_text = _read_text(interface_dir / "cli.md")
    module_name = slug.replace("-", "_")
    try:
        module = _load_module(repo_root, gen_dir, module_name)
        drift = _check_interface_drift(module, library_text, cli_text)
    except Exception:
        drift = True

    if gt_test_files:
        baseline = _run_pytest(gt_test_files, cwd=gen_dir, pythonpath=gen_dir, timeout=10.0)
        timeout = max(10.0, 10.0 * baseline["duration"])
        mutation_score = _compute_mutation_score(gen_dir, module_name, gt_test_files, timeout)
    else:
        mutation_score = 1.0

    criteria_out = []
    for c in criteria_meta:
        cid, covers, kind = c["id"], c["covers"], c["kind"]
        if kind == "compiled":
            r = compiled_results.get(cid) or {
                "result": "fail",
                "failure_detail": {"message": "not evaluated", "expected": None, "actual": None},
            }
        elif kind == "generated-test":
            r = gt_results.get(cid) or {
                "result": "fail",
                "failure_detail": {"message": "not evaluated", "expected": None, "actual": None},
            }
        elif kind == "llm-judge":
            r = lj_results.get(cid) or {"result": "skipped", "rationale": None}
        else:
            r = {
                "result": "fail",
                "failure_detail": {"message": f"unrecognized kind '{kind}'", "expected": None, "actual": None},
            }
        entry = {"id": cid, "covers": covers, "kind": kind}
        entry.update(r)
        criteria_out.append(entry)

    requirement_pass = {}
    for entry in criteria_out:
        cover = entry.get("covers")
        if not cover:
            continue
        ok = entry["result"] == "pass"
        requirement_pass[cover] = requirement_pass.get(cover, True) and ok
    requirement_results = {k: ("pass" if v else "fail") for k, v in requirement_pass.items()}

    has_generated_test = any(c["kind"] == "generated-test" for c in criteria_meta)
    overall_fail = drift
    for entry in criteria_out:
        if entry["kind"] in ("compiled", "generated-test") and entry["result"] == "fail":
            overall_fail = True
        if entry["kind"] == "llm-judge" and entry["result"] == "fail":
            overall_fail = True
    if has_generated_test and mutation_score < MUTATION_SCORE_BAR:
        overall_fail = True

    return VerificationReport(
        component_id=component_id,
        criteria=criteria_out,
        requirement_results=requirement_results,
        interface_drift=drift,
        mutation_score=mutation_score,
        overall="fail" if overall_fail else "pass",
    )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="hotdocs verify")
    parser.add_argument("component_id")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--format", choices=["json", "text"], default="text")
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        code = exc.code
        return code if isinstance(code, int) else 2

    repo_root = Path(args.repo_root).resolve()
    report = verify(args.component_id, repo_root)

    if args.format == "json":
        print(json.dumps(dataclasses.asdict(report), indent=2))
    else:
        print(f"{report.component_id}: {report.overall}")
        for c in report.criteria:
            print(f"  {c['id']} [{c['kind']}] -> {c['result']}")
        print(f"  interface_drift: {report.interface_drift}")
        print(f"  mutation_score: {report.mutation_score}")

    return 0 if report.overall == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())