"""Verifier orchestrator: runs every verification gate against one component."""

from __future__ import annotations

import ast
import hashlib
import importlib.util
import inspect
import json
import os
import re
import signal
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from pathlib import Path

GATE_VERSION = "verifier-orchestrator@4.0.0"
DEFAULT_TEST_TIMEOUT = 300.0

_USAGE = "usage: hotdocs verify-component <component-id> [--repo-root=<dir>] [--format=json|text]"

_CONFTEST = '''import json
import os


def pytest_assertrepr_compare(config, op, left, right):
    path = {path!r}
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({{"op": op, "left": repr(left), "right": repr(right)}}, fh)
    return None
'''


@dataclass
class VerificationReport:
    component_id: str
    criteria: list
    requirement_results: dict
    interface_drift: bool
    mutation_score: object
    mutation_error: object
    assets: list
    drivers: list
    overall: str

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------- helpers


def _get(obj, key):
    return obj.get(key) if isinstance(obj, dict) else getattr(obj, key, None)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def _slug(component_id: str) -> str:
    return re.sub(r"^comp-", "", component_id)


def _tool_root() -> Path:
    here = Path(os.path.abspath(__file__))
    return next(p.parent for p in here.parents if p.name == "gen")


def _load_from(code_dir: Path, module_name: str):
    pkg = code_dir / module_name / "__init__.py"
    if pkg.is_file():
        file = pkg
        locations = [str(pkg.parent)]
    else:
        file = code_dir / f"{module_name}.py"
        locations = None
    name = "_hotdocs_vo_%s_%s" % (
        module_name,
        hashlib.sha256(str(file).encode("utf-8")).hexdigest()[:16],
    )
    spec = importlib.util.spec_from_file_location(
        name, str(file), submodule_search_locations=locations
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    old = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = old
    return module


def _load(repo_root: Path, rel_dir: str, module_name: str):
    base = repo_root / rel_dir
    if not base.is_dir():
        base = _tool_root() / rel_dir
    return _load_from(base, module_name)


def _kill_tree(root: int) -> None:
    listing = subprocess.run(
        ["ps", "-eo", "pid=,ppid="], capture_output=True, text=True
    ).stdout
    children: dict = {}
    for line in listing.splitlines():
        pid, ppid = (int(x) for x in line.split())
        children.setdefault(ppid, []).append(pid)
    found, stack = [], [root]
    while stack:
        for child in children.get(stack.pop(), []):
            found.append(child)
            stack.append(child)
    for pid in found + [root]:
        try:
            os.kill(pid, signal.SIGKILL)
        except OSError:
            pass


def _run(cmd: list, env: dict, cwd: Path):
    with tempfile.TemporaryFile() as out:
        proc = subprocess.Popen(
            cmd, cwd=str(cwd), env=env, stdout=out, stderr=subprocess.STDOUT
        )
        try:
            rc = proc.wait(timeout=DEFAULT_TEST_TIMEOUT)
        except subprocess.TimeoutExpired:
            _kill_tree(proc.pid)
            proc.wait()
            rc = None
        out.seek(0)
        return rc, out.read().decode("utf-8", "replace")


def _message(rc, output: str) -> str:
    if rc is None:
        return f"test timed out after {DEFAULT_TEST_TIMEOUT} seconds"
    m = re.search(r"^>\s+assert\s+(.+?)\s*$", output, re.M)
    if m:
        return m.group(1).replace(" == ", " equals ", 1) + " failed"
    return f"test run exited with code {rc}"


def _literal(text: str):
    try:
        return ast.literal_eval(text)
    except Exception:
        return None


# ---------------------------------------------------------------- parsing


def _frontmatter(text: str) -> str:
    m = re.match(r"---\n(.*?)\n---", text, re.S)
    return m.group(1) if m else ""


def _parse_criteria(spec_dir: Path) -> list:
    criteria = []
    for path in sorted((spec_dir / "acceptance").glob("*.md")):
        text = _read(path)
        cid = re.search(r"^#\s+(AC-[A-Za-z0-9-]+)", text, re.M).group(1)
        cov = re.search(r"Covers:\**\s*`?(?:@covers:)?([A-Z]-[A-Za-z0-9-]+)", text)
        kind = re.search(
            r"^Kind:\s*`?(compiled|generated-test|llm-judge)", text[cov.end():], re.M
        ).group(1)
        criteria.append({
            "id": cid,
            "covers": cov.group(1),
            "kind": kind,
            "freeform": re.search(r"^\s*```gherkin\s*$", text, re.M) is None,
        })
    return criteria


def _documented(text: str) -> list:
    blocks, current, inside = [], [], False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            if inside:
                blocks.append("\n".join(current))
                current = []
            inside = not inside
        elif inside:
            current.append(line)
    found = []
    for block in blocks:
        for m in re.finditer(r"^[ \t]*(?:def[ \t]+)?([A-Za-z_][\w.]*)\(", block, re.M):
            depth, i = 1, m.end()
            while depth:
                ch = block[i]
                depth += (ch in "([{") - (ch in ")]}")
                i += 1
            found.append((m.group(1), _param_names(block[m.end():i - 1])))
    return found


def _param_names(inner: str) -> list:
    parts, depth, cur = [], 0, ""
    for ch in inner:
        depth += (ch in "([{") - (ch in ")]}")
        if ch == "," and depth == 0:
            parts.append(cur)
            cur = ""
        else:
            cur += ch
    parts.append(cur)
    names = []
    for part in parts:
        m = re.match(r"\s*\**([A-Za-z_]\w*)", part)
        if m:
            names.append(m.group(1))
    return names


def _drift(code_dir: Path, module_name: str, spec_dir: Path) -> bool:
    iface = spec_dir / "interface"
    documented = _documented(_read(iface / "library.md")) + _documented(_read(iface / "cli.md"))
    if (iface / "cli.md").is_file():
        documented.append(("main", ["argv"]))
    try:
        module = _load_from(code_dir, module_name)
    except Exception:
        return True
    for name, params in documented:
        obj = module
        try:
            for part in name.split("."):
                obj = getattr(obj, part)
            sig = inspect.signature(obj)
        except (AttributeError, TypeError, ValueError):
            return True
        if [p.name for p in sig.parameters.values()] != params:
            return True
    return False


# ---------------------------------------------------------------- entries


def _entry(c: dict, result: str, **extra) -> dict:
    entry = {"id": c["id"], "covers": c["covers"], "kind": c["kind"], "result": result}
    entry.update(extra)
    return entry


def _fail(entry: dict, origin: str, message, expected=None, actual=None) -> dict:
    entry["result"] = "fail"
    entry["failure_detail"] = {"message": message, "expected": expected, "actual": actual}
    entry["failure_origin"] = origin
    return entry


def _judge(c: dict, component_id: str, repo_root: Path, judge) -> dict:
    if judge is None:
        return _entry(c, "skipped", rationale=None)
    assembler = _load(repo_root, "gen/spec-bundle-assembler", "spec_bundle_assembler")
    bundle = assembler.assemble_criterion(component_id, c["id"], repo_root)
    outcome = judge(bundle)
    if isinstance(outcome, dict):
        value = outcome.get("result", outcome.get("verdict"))
        rationale = outcome.get("rationale")
    else:
        value, rationale = outcome, None
    result = "pass" if value is True or value == "pass" else "fail"
    return _entry(c, result, rationale=rationale)


def _requirement_results(spec_dir: Path, entries: list) -> dict:
    results = {}
    for rid in sorted(p.stem for p in (spec_dir / "requirements").glob("R-*.md")):
        covering = [e["result"] for e in entries if e["covers"] == rid]
        results[rid] = "pass" if all(r == "pass" for r in covering) else "fail"
    return results


# ---------------------------------------------------------------- verify


def verify(component_id: str, repo_root: Path, judge=None, test_author=None) -> VerificationReport:
    repo_root = Path(repo_root).absolute()
    slug = _slug(component_id)
    module_name = slug.replace("-", "_")
    spec_dir = repo_root / "specs" / "components" / slug
    criteria = _parse_criteria(spec_dir)
    fm = _frontmatter(_read(spec_dir / "component.md"))
    sealed = re.search(r"^sealed:\s*true\s*$", fm, re.M)
    source = re.search(r"^source_path:\s*(\S.*?)\s*$", fm, re.M)
    if sealed and source:
        return _verify_sealed(
            component_id, repo_root, slug, module_name, spec_dir, criteria,
            repo_root / source.group(1).strip("'\""), judge,
        )
    return _verify_unsealed(
        component_id, repo_root, slug, module_name, spec_dir, criteria, judge, test_author
    )


def _verify_sealed(component_id, repo_root, slug, module_name, spec_dir, criteria, code_dir, judge):
    drift = _drift(code_dir, module_name, spec_dir)
    files = sorted((repo_root / "verification" / slug).glob("test_*.py"))
    names = {}
    outcomes = {}
    env = dict(os.environ)
    env["PYTHONPATH"] = str(code_dir)
    with tempfile.TemporaryDirectory() as work:
        for index, file in enumerate(files):
            names[file] = re.findall(
                r"^\s*(?:async\s+)?def\s+(test_\w+)\s*\(", _read(file), re.M
            )
            xml_path = Path(work) / f"junit_{index}.xml"
            _run(
                [sys.executable, "-m", "pytest", str(file), "-p", "no:cacheprovider",
                 f"--junitxml={xml_path}"],
                env, repo_root,
            )
            if xml_path.is_file():
                for case in ET.parse(str(xml_path)).getroot().iter("testcase"):
                    key = (file, case.get("name", "").split("[")[0])
                    ok = not any(ch.tag in ("failure", "error", "skipped") for ch in case)
                    outcomes[key] = outcomes.get(key, True) and ok
    entries = []
    for c in criteria:
        if c["kind"] == "llm-judge":
            entries.append(_judge(c, component_id, repo_root, judge))
            continue
        prefix = "test_" + c["id"].lower().replace("-", "_")
        matches = [
            (f, n) for f in files for n in names[f]
            if n == prefix or n.startswith(prefix + "_")
        ]
        entry = _entry(c, "pass")
        failing = [n for f, n in matches if outcomes.get((f, n)) is not True]
        if not matches:
            _fail(entry, "implementation", "no characterization test")
        elif failing:
            _fail(entry, "implementation", "characterization test failed: " + ", ".join(failing))
        entries.append(entry)
    failed = drift or any(e["result"] == "fail" for e in entries)
    return VerificationReport(
        component_id=component_id,
        criteria=entries,
        requirement_results=_requirement_results(spec_dir, entries),
        interface_drift=drift,
        mutation_score=None,
        mutation_error=None,
        assets=[],
        drivers=[],
        overall="fail" if failed else "pass",
    )


def _verify_unsealed(component_id, repo_root, slug, module_name, spec_dir, criteria, judge, test_author):
    run_env_mod = _load(repo_root, "gen/run-environment", "run_environment")
    env = run_env_mod.prepare(component_id, repo_root)
    code_dir = repo_root / "gen" / slug
    try:
        drift = _drift(code_dir, module_name, spec_dir)
        ok = _get(env, "ok")
        entries = []
        passed = []
        mutation_score = None
        mutation_error = None
        mutation_fail = False
        with tempfile.TemporaryDirectory() as work:
            work = Path(work)
            compiled = {}
            run_env = {}
            base_cmd = []
            if ok:
                run_env = dict(os.environ)
                run_env.update(_get(env, "env_for")(code_dir))
                run_env["PYTHONPATH"] = os.pathsep.join(
                    [str(code_dir), str(_get(env, "plugin_dir"))]
                )
                base_cmd = [_get(env, "interpreter"), "-m", "pytest"]
                extra_args = list(_get(env, "pytest_args")()) + ["-p", "no:cacheprovider"]
            record = work / "compare.json"
            if ok and any(c["kind"] == "compiled" for c in criteria):
                compiler = _load(repo_root, "pipeline/criterion-compiler", "criterion_compiler")
                out_dir = work / "compiled"
                report = compiler.compile(component_id, repo_root, out_dir=out_dir)
                compiled = {_get(o, "criterion_id"): o for o in _get(report, "outputs")}
                out_dir.mkdir(parents=True, exist_ok=True)
                (out_dir / "conftest.py").write_text(
                    _CONFTEST.format(path=str(record)), encoding="utf-8"
                )
            supply_mod = None
            for c in criteria:
                if c["kind"] == "llm-judge":
                    entries.append(_judge(c, component_id, repo_root, judge))
                    continue
                entry = _entry(c, "pass")
                if not ok:
                    entries.append(_fail(entry, "environment", _get(env, "failure_message")))
                    continue
                if c["kind"] == "compiled":
                    out = compiled.get(
                        c["id"], {"status": "error", "message": "criterion was not compiled"}
                    )
                    if _get(out, "status") != "compiled":
                        _fail(entry, "test", _get(out, "message"))
                    else:
                        record.unlink(missing_ok=True)
                        file = repo_root / _get(out, "file")
                        rc, output = _run(base_cmd + [str(file)] + extra_args, run_env, repo_root)
                        if rc != 0:
                            expected = actual = None
                            if record.is_file():
                                rec = json.loads(record.read_text(encoding="utf-8"))
                                left, right = _literal(rec["left"]), _literal(rec["right"])
                                expected, actual = (right, left) if rec["op"] == "==" else (left, right)
                            _fail(entry, "implementation", _message(rc, output), expected, actual)
                    entries.append(entry)
                    continue
                if supply_mod is None:
                    supply_mod = _load(repo_root, "gen/test-supply", "test_supply")
                supplied = supply_mod.supply(
                    component_id, c["id"], repo_root,
                    test_author=test_author,
                    interpreter=_get(env, "interpreter"),
                    assets=[_get(a, "path") for a in list(_get(env, "assets"))[1:]],
                    drivers=list(_get(env, "driver_fixtures")()),
                )
                authoring = _get(supplied, "test_authoring")
                if authoring is not None:
                    entry["test_authoring"] = dict(authoring)
                if _get(supplied, "failure_origin") == "test":
                    _fail(entry, "test", _get(supplied, "failure_message"))
                else:
                    path = os.path.abspath(_get(supplied, "path"))
                    rc, output = _run(base_cmd + [path] + extra_args, run_env, repo_root)
                    if rc == 0:
                        passed.append((path, len(entries)))
                    else:
                        _fail(entry, "implementation", _message(rc, output))
                entries.append(entry)
        if ok:
            scorer = _load(repo_root, "gen/mutation-scorer", "mutation_scorer")
            result = scorer.score(component_id, repo_root, [p for p, _ in passed], env)
            faulty = set(_get(result, "faulty_tests"))
            for path, index in passed:
                if path in faulty:
                    _fail(entries[index], "test", "test fails in the mutation sandbox")
                    if supply_mod is None:
                        supply_mod = _load(repo_root, "gen/test-supply", "test_supply")
                    supply_mod.discard(component_id, entries[index]["id"], repo_root)
            mutation_score = _get(result, "mutation_score")
            mutation_error = _get(result, "mutation_error")
            freeform = any(c["kind"] == "generated-test" and c["freeform"] for c in criteria)
            threshold = 0.9 if freeform else 0.8
            mutation_fail = mutation_error is not None or (
                mutation_score is not None and mutation_score < threshold
            )
        failed = drift or mutation_fail or any(e["result"] == "fail" for e in entries)
        return VerificationReport(
            component_id=component_id,
            criteria=entries,
            requirement_results=_requirement_results(spec_dir, entries),
            interface_drift=drift,
            mutation_score=mutation_score,
            mutation_error=mutation_error,
            assets=list(_get(env, "assets")),
            drivers=list(_get(env, "drivers")),
            overall="fail" if failed else "pass",
        )
    finally:
        _get(env, "close")()


# ---------------------------------------------------------------- CLI


def _usage(cause: str) -> int:
    print(f"usage error: {cause}", file=sys.stderr)
    print(_USAGE, file=sys.stderr)
    return 2


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    opts = {"--repo-root": ".", "--format": "text"}
    component_id = None
    i = 0
    while i < len(args):
        token = args[i]
        flag, eq, value = token.partition("=")
        if flag in opts:
            if not eq:
                i += 1
                if i == len(args):
                    return _usage(f"{flag} needs a value")
                value = args[i]
            opts[flag] = value
        elif component_id is None and not token.startswith("-"):
            component_id = token
        else:
            return _usage(f"unknown argument: {token}")
        i += 1
    if component_id is None:
        return _usage("missing <component-id>")
    if opts["--format"] not in ("json", "text"):
        return _usage(f"invalid --format: {opts['--format']}")
    repo_root = Path(opts["--repo-root"])
    if not (repo_root / "specs" / "components" / _slug(component_id) / "component.md").is_file():
        return _usage(f"unknown component: {component_id}")
    report = verify(component_id, repo_root)
    if opts["--format"] == "json":
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print(f"{component_id}: {report.overall}")
        for c in report.criteria:
            print(f"  {c['id']}: {c['result']}")
    return 0 if report.overall == "pass" else 1
