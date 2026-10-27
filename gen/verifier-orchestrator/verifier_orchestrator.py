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
from dataclasses import dataclass, asdict
from pathlib import Path

MUTATION_SCORE_BAR = 0.8

_COVERS_RE = re.compile(r"(?im)^\**covers\**\s*:\**\s*(R-[A-Za-z0-9][\w-]*(?:\s*,\s*R-[A-Za-z0-9][\w-]*)*)")
_KIND_RE = re.compile(r"(?im)^\**kind\**\s*:\**\s*`?(compiled|generated-test|llm-judge)`?")
_FENCE_RE = re.compile(r"```[a-zA-Z0-9]*\n(.*?)```", re.S)
_ASSERT_RE = re.compile(r"^assert\s+(.+?)\s+(not in|is not|==|!=|in|is)\s+(.+)$")

_CMP_SWAP = {
    ast.Eq: ast.NotEq, ast.NotEq: ast.Eq,
    ast.Lt: ast.GtE, ast.GtE: ast.Lt,
    ast.Gt: ast.LtE, ast.LtE: ast.Gt,
    ast.Is: ast.IsNot, ast.IsNot: ast.Is,
}


@dataclass
class ParsedAC:
    id: str
    covers: str
    kind: str
    text: str
    file: Path


@dataclass
class CriterionBundle:
    component_id: str
    criterion_id: str
    covers: str
    criterion_text: str
    requirement_text: str
    interface: str
    glossary: str


@dataclass
class VerificationReport:
    component_id: str
    criteria: list
    requirement_results: dict
    interface_drift: bool
    mutation_score: float
    overall: str


def _slug(component_id: str) -> str:
    return component_id[len("comp-"):] if component_id.startswith("comp-") else component_id


def _load_module_from_dir(base_dir: Path, module_name: str):
    pkg_init = base_dir / module_name / "__init__.py"
    flat_file = base_dir / f"{module_name}.py"
    if pkg_init.is_file():
        path = pkg_init
        search_locations = [str(path.parent)]
    elif flat_file.is_file():
        path = flat_file
        search_locations = None
    else:
        return None
    try:
        spec = importlib.util.spec_from_file_location(module_name, path, submodule_search_locations=search_locations)
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        return module
    except Exception:
        sys.modules.pop(module_name, None)
        return None


def _parse_acceptance_dir(acceptance_dir: Path):
    results = []
    if not acceptance_dir.is_dir():
        return results
    for path in sorted(acceptance_dir.glob("*.md")):
        text = path.read_text()
        covers_match = _COVERS_RE.search(text)
        kind_match = _KIND_RE.search(text)
        covers = covers_match.group(1).strip() if covers_match else ""
        kind = kind_match.group(1).strip() if kind_match else ""
        results.append(ParsedAC(id=path.stem, covers=covers, kind=kind, text=text, file=path))
    return results


def _read_interface_text(interface_dir: Path) -> str:
    parts = []
    if interface_dir.is_dir():
        for path in sorted(interface_dir.rglob("*.md")):
            parts.append(path.read_text())
    return "\n\n".join(parts)


def _read_requirement_text(repo_root: Path, slug: str, covers: str) -> str:
    req_dir = repo_root / "specs" / "components" / slug / "requirements"
    texts = []
    for rid in [r.strip() for r in covers.split(",") if r.strip()]:
        path = req_dir / f"{rid}.md"
        if path.is_file():
            texts.append(path.read_text())
    return "\n\n".join(texts)


def _read_glossary(repo_root: Path) -> str:
    path = repo_root / "specs" / "glossary.md"
    return path.read_text() if path.is_file() else ""


def _build_criterion_bundle(component_id: str, slug: str, criterion: ParsedAC, interface_dir: Path, repo_root: Path) -> CriterionBundle:
    return CriterionBundle(
        component_id=component_id,
        criterion_id=criterion.id,
        covers=criterion.covers,
        criterion_text=criterion.text,
        requirement_text=_read_requirement_text(repo_root, slug, criterion.covers),
        interface=_read_interface_text(interface_dir),
        glossary=_read_glossary(repo_root),
    )


def _try_literal(text: str):
    try:
        return ast.literal_eval(text.strip())
    except (ValueError, SyntaxError):
        return None


def _parse_failure_detail(stdout: str, stderr: str = "") -> dict:
    assert_line = None
    for line in stdout.splitlines():
        s = line.strip()
        if s.startswith("E "):
            assert_line = s[1:].strip()
            break
    message = assert_line
    expected = None
    actual = None
    if assert_line:
        m = _ASSERT_RE.match(assert_line)
        if m:
            lhs, _op, rhs = m.groups()
            actual = _try_literal(lhs)
            expected = _try_literal(rhs)
    if message is None:
        for line in reversed(stdout.splitlines()):
            if line.strip():
                message = line.strip()
                break
    if message is None:
        for line in reversed(stderr.splitlines()):
            if line.strip():
                message = line.strip()
                break
    return {"message": message or "test failed", "expected": expected, "actual": actual}


def _run_pytest(test_file: Path, import_root: Path) -> dict:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(import_root)
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", str(test_file), "-q", "--tb=short", "-p", "no:cacheprovider"],
        capture_output=True, text=True, env=env, cwd=str(import_root),
    )
    return {"passed": proc.returncode == 0, "stdout": proc.stdout, "stderr": proc.stderr}


def _iter_signatures(markdown_text: str):
    for fence in _FENCE_RE.findall(markdown_text):
        pos = 0
        while True:
            m = re.search(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\(", fence[pos:])
            if not m:
                break
            open_paren = pos + m.end() - 1
            depth = 0
            end = open_paren
            for i in range(open_paren, len(fence)):
                if fence[i] == "(":
                    depth += 1
                elif fence[i] == ")":
                    depth -= 1
                    if depth == 0:
                        end = i
                        break
            yield m.group(1), fence[open_paren + 1:end]
            pos = end + 1


def _parse_params(params_text: str):
    depth = 0
    current = ""
    parts = []
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
        name = re.split(r"[:=]", part, 1)[0].strip()
        if name:
            names.append(name)
    return names


def _check_interface_drift(module, interface_dir: Path) -> bool:
    drift = False
    lib_md = interface_dir / "library.md"
    if lib_md.is_file():
        for name, params_text in _iter_signatures(lib_md.read_text()):
            documented_params = _parse_params(params_text)
            obj = getattr(module, name, None) if module is not None else None
            if obj is None or not callable(obj):
                drift = True
                continue
            try:
                actual_params = list(inspect.signature(obj).parameters.keys())
            except (TypeError, ValueError):
                drift = True
                continue
            if actual_params != documented_params:
                drift = True
    cli_md = interface_dir / "cli.md"
    if cli_md.is_file() and cli_md.read_text().strip():
        obj = getattr(module, "main", None) if module is not None else None
        if obj is None or not callable(obj):
            drift = True
    return drift


def _mutable_nodes(tree):
    nodes = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare) and len(node.ops) == 1 and type(node.ops[0]) in _CMP_SWAP:
            nodes.append(node)
        elif isinstance(node, ast.BoolOp):
            nodes.append(node)
        elif isinstance(node, ast.Constant) and isinstance(node.value, bool):
            nodes.append(node)
        elif isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            nodes.append(node)
    return nodes


def _apply_mutation(node):
    if isinstance(node, ast.Compare):
        node.ops[0] = _CMP_SWAP[type(node.ops[0])]()
    elif isinstance(node, ast.BoolOp):
        node.op = ast.Or() if isinstance(node.op, ast.And) else ast.And()
    elif isinstance(node, ast.Constant) and isinstance(node.value, bool):
        node.value = not node.value
    elif isinstance(node, ast.Constant):
        node.value = node.value + 1


def _generate_mutants(source_path: Path):
    source = source_path.read_text()
    tree = ast.parse(source, filename=str(source_path))
    count = len(_mutable_nodes(tree))
    mutants = []
    for idx in range(count):
        mutant_tree = ast.parse(source, filename=str(source_path))
        nodes = _mutable_nodes(mutant_tree)
        _apply_mutation(nodes[idx])
        ast.fix_missing_locations(mutant_tree)
        mutants.append(ast.unparse(mutant_tree))
    return mutants


def _any_test_fails(test_files, import_root: Path) -> bool:
    for test_file in test_files:
        if not _run_pytest(test_file, import_root)["passed"]:
            return True
    return False


def _compute_mutation_score(gen_dir: Path, test_files: dict) -> float:
    if not test_files:
        return 1.0
    total = 0
    killed = 0
    for py_file in sorted(gen_dir.rglob("*.py")):
        rel = py_file.relative_to(gen_dir)
        try:
            mutants = _generate_mutants(py_file)
        except SyntaxError:
            continue
        for mutant_source in mutants:
            total += 1
            with tempfile.TemporaryDirectory() as tmp:
                sandbox = Path(tmp) / gen_dir.name
                shutil.copytree(gen_dir, sandbox, ignore=shutil.ignore_patterns("__pycache__"))
                (sandbox / rel).write_text(mutant_source)
                if _any_test_fails(test_files.values(), sandbox):
                    killed += 1
    if total == 0:
        return 1.0
    return killed / total


def _extract_judge_outcome(outcome):
    if isinstance(outcome, dict):
        value = outcome.get("result", outcome.get("verdict"))
        rationale = outcome.get("rationale")
    else:
        value = outcome
        rationale = None
    if isinstance(value, bool):
        return ("pass" if value else "fail"), rationale
    if isinstance(value, str):
        v = value.strip().lower()
        if v in ("pass", "true", "passed"):
            return "pass", rationale
        if v in ("fail", "false", "failed"):
            return "fail", rationale
    return "fail", rationale


def _extract_test_authoring(outcome):
    if isinstance(outcome, dict):
        get = outcome.get
    else:
        get = lambda k, default=None: getattr(outcome, k, default)
    return {
        "model_call_error": get("model_call_error"),
        "file": get("file"),
        "model": get("model"),
        "seed": get("seed"),
        "prompt_version": get("prompt_version"),
        "cache_hit": get("cache_hit", False),
    }


def verify(component_id: str, repo_root: Path, judge=None, test_author=None) -> VerificationReport:
    repo_root = Path(repo_root)
    slug = _slug(component_id)
    gen_dir = repo_root / "gen" / slug
    comp_dir = repo_root / "specs" / "components" / slug
    acceptance_dir = comp_dir / "acceptance"
    interface_dir = comp_dir / "interface"
    module_name = slug.replace("-", "_")

    parsed_criteria = _parse_acceptance_dir(acceptance_dir)
    compiled_criteria = [c for c in parsed_criteria if c.kind == "compiled"]
    generated_criteria = [c for c in parsed_criteria if c.kind == "generated-test"]
    judge_criteria = [c for c in parsed_criteria if c.kind == "llm-judge"]

    criteria_results = []

    compile_outputs = {}
    if compiled_criteria:
        cc = _load_module_from_dir(repo_root / "pipeline" / "criterion-compiler", "criterion_compiler")
        if cc is None:
            raise RuntimeError("criterion-compiler module not found under pipeline/criterion-compiler/")
        compile_out_dir = repo_root / "verification" / slug / "compiled"
        compile_report = cc.compile(component_id, repo_root, target="pytest", out_dir=compile_out_dir)
        compile_outputs = {o["criterion_id"]: o for o in compile_report.outputs}

    for c in compiled_criteria:
        entry = {"id": c.id, "covers": c.covers, "kind": "compiled"}
        out = compile_outputs.get(c.id)
        if out is None:
            entry["result"] = "fail"
            entry["failure_detail"] = {"message": f"criterion {c.id} was not compiled", "expected": None, "actual": None}
        elif out["status"] == "error":
            entry["result"] = "fail"
            entry["failure_detail"] = {"message": out.get("message", "compile error"), "expected": None, "actual": None}
        else:
            test_file = Path(out["file"])
            if not test_file.is_absolute():
                test_file = repo_root / test_file
            run = _run_pytest(test_file, gen_dir)
            if run["passed"]:
                entry["result"] = "pass"
            else:
                entry["result"] = "fail"
                entry["failure_detail"] = _parse_failure_detail(run["stdout"], run["stderr"])
        criteria_results.append(entry)

    generated_test_dir = repo_root / "verification" / slug / "generated-test"
    generated_test_files = {}
    for c in generated_criteria:
        entry = {"id": c.id, "covers": c.covers, "kind": "generated-test"}
        filename = f"test_{c.id.lower().replace('-', '_')}.py"
        cached_path = generated_test_dir / filename

        if cached_path.is_file():
            test_path = cached_path
        elif test_author is not None:
            bundle = _build_criterion_bundle(component_id, slug, c, interface_dir, repo_root)
            authoring = _extract_test_authoring(test_author(bundle))
            if authoring["model_call_error"]:
                entry["result"] = "fail"
                entry["failure_detail"] = {"message": str(authoring["model_call_error"]), "expected": None, "actual": None}
                criteria_results.append(entry)
                continue
            file_info = authoring["file"]
            if not file_info:
                entry["result"] = "fail"
                entry["failure_detail"] = {"message": "test_author returned no file", "expected": None, "actual": None}
                criteria_results.append(entry)
                continue
            generated_test_dir.mkdir(parents=True, exist_ok=True)
            content = file_info["content"] if isinstance(file_info, dict) else file_info.content
            cached_path.write_text(content)
            test_path = cached_path
            entry["test_authoring"] = {
                "model": authoring["model"],
                "seed": authoring["seed"],
                "prompt_version": authoring["prompt_version"],
                "cache_hit": authoring["cache_hit"],
            }
        else:
            entry["result"] = "fail"
            entry["failure_detail"] = {"message": "no cached test and no test_author configured", "expected": None, "actual": None}
            criteria_results.append(entry)
            continue

        generated_test_files[c.id] = test_path
        run = _run_pytest(test_path, gen_dir)
        if run["passed"]:
            entry["result"] = "pass"
        else:
            entry["result"] = "fail"
            entry["failure_detail"] = _parse_failure_detail(run["stdout"], run["stderr"])
        criteria_results.append(entry)

    for c in judge_criteria:
        entry = {"id": c.id, "covers": c.covers, "kind": "llm-judge"}
        if judge is None:
            entry["result"] = "skipped"
            entry["rationale"] = None
        else:
            bundle = _build_criterion_bundle(component_id, slug, c, interface_dir, repo_root)
            result, rationale = _extract_judge_outcome(judge(bundle))
            entry["result"] = result
            entry["rationale"] = rationale
        criteria_results.append(entry)

    module = _load_module_from_dir(gen_dir, module_name)
    interface_drift = _check_interface_drift(module, interface_dir)

    mutation_score = _compute_mutation_score(gen_dir, generated_test_files) if generated_criteria else 1.0

    requirement_pass_map = {}
    for entry in criteria_results:
        ok = entry["result"] == "pass"
        for rid in [r.strip() for r in entry["covers"].split(",") if r.strip()]:
            requirement_pass_map.setdefault(rid, []).append(ok)
    requirement_results = {rid: ("pass" if all(oks) else "fail") for rid, oks in requirement_pass_map.items()}

    overall = "pass"
    for entry in criteria_results:
        if entry["kind"] in ("compiled", "generated-test") and entry["result"] == "fail":
            overall = "fail"
        elif entry["kind"] == "llm-judge" and entry["result"] == "fail":
            overall = "fail"
    if interface_drift:
        overall = "fail"
    if generated_criteria and mutation_score < MUTATION_SCORE_BAR:
        overall = "fail"

    return VerificationReport(
        component_id=component_id,
        criteria=criteria_results,
        requirement_results=requirement_results,
        interface_drift=interface_drift,
        mutation_score=mutation_score,
        overall=overall,
    )


def _default_repo_root() -> Path:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, check=True,
        )
        return Path(out.stdout.strip())
    except Exception:
        return Path.cwd()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="hotdocs verify")
    parser.add_argument("component_id")
    parser.add_argument("--repo-root", default=None)
    parser.add_argument("--format", choices=["json", "text"], default="text")
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return exc.code if exc.code is not None else 2

    repo_root = Path(args.repo_root) if args.repo_root else _default_repo_root()
    report = verify(args.component_id, repo_root)

    if args.format == "json":
        print(json.dumps(asdict(report), indent=2))
    else:
        print(f"{report.component_id}: {report.overall}")
        for c in report.criteria:
            print(f"  {c['id']} [{c['kind']}] {c['result']}")

    return 0 if report.overall == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())