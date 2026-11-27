"""Verifier orchestrator: runs every verification gate against one component."""

import ast
import dataclasses
import hashlib
import importlib.util
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

GATE_VERSION = "verifier-orchestrator@4.0.0"
DEFAULT_TEST_TIMEOUT = 300.0

USAGE = "usage: hotdocs verify-component <component-id> [--repo-root=<dir>] [--format=json|text]"

_AC_HEADING = re.compile(r"^# (AC-[A-Z0-9]+(?:-[A-Z0-9]+)*[a-z]?)", re.M)
_COVERS = re.compile(r"Covers:\s*`?([RP]-[A-Za-z0-9-]*[A-Za-z0-9])")
_KIND = re.compile(r"^Kind:\s*`?([a-z-]+)", re.M)
_GHERKIN = re.compile(r"^```gherkin\s*$", re.M)
_CALL = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*\(")
_PARAM = re.compile(r"\s*\**([A-Za-z_][A-Za-z0-9_]*)")
_TEST_DEF = re.compile(r"^\s*def\s+(test_[A-Za-z0-9_]*)\s*\(", re.M)

_CONFTEST = '''import json
import os


def _record(key, value):
    path = os.environ["HOTDOCS_VO_CAPTURE"]
    data = {}
    if os.path.exists(path):
        with open(path) as handle:
            data = json.load(handle)
    data.setdefault(key, value)
    with open(path, "w") as handle:
        json.dump(data, handle)


def pytest_assertrepr_compare(config, op, left, right):
    _record("compare", [op, repr(left), repr(right)])
    return None


def pytest_runtest_logreport(report):
    if report.failed:
        crash = getattr(report.longrepr, "reprcrash", None)
        text = crash.message if crash is not None else str(report.longrepr)
        _record("message", text.split("\\n")[0])
'''

_DRIFT_SCRIPT = '''import importlib, inspect, json, sys
sys.path.pop(0)
names = json.loads(sys.argv[2])
try:
    module = importlib.import_module(sys.argv[1])
except Exception:
    module = None
out = {}
for name in names:
    obj = module
    try:
        for part in name.split("."):
            obj = getattr(obj, part)
        out[name] = [p.name for p in inspect.signature(obj).parameters.values()]
    except Exception:
        out[name] = None
print(json.dumps(out))
'''


@dataclasses.dataclass
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

    def to_dict(self):
        return dataclasses.asdict(self)


def _get(obj, name):
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


def _tool_root():
    for parent in Path(__file__).resolve().parents:
        if parent.name == "gen":
            return parent.parent


def _load(repo_root, rel_dir, module_name):
    base = repo_root / rel_dir
    if not base.is_dir():
        base = _tool_root() / rel_dir
    path = base / f"{module_name}.py"
    digest = hashlib.sha256(str(path).encode("utf-8")).hexdigest()[:16]
    name = f"_hotdocs_vo_{module_name}_{digest}"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _frontmatter(text):
    match = re.match(r"---\s*\n(.*?)\n---", text, re.S)
    body = match.group(1) if match else ""
    return {k: v.strip() for k, v in re.findall(r"^([A-Za-z_]+):(.*)$", body, re.M)}


def _read_criteria(comp_dir):
    criteria = []
    for path in sorted((comp_dir / "acceptance").glob("*.md")):
        text = path.read_text(encoding="utf-8")
        covers = _COVERS.search(text)
        kind = _KIND.search(text, covers.end())
        criteria.append({
            "id": _AC_HEADING.search(text).group(1),
            "covers": covers.group(1),
            "kind": kind.group(1),
            "freeform": _GHERKIN.search(text) is None,
        })
    return criteria


def _params(rest):
    depth = 1
    parts = [""]
    for ch in rest:
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        if depth == 0:
            break
        if ch == "," and depth == 1:
            parts.append("")
        else:
            parts[-1] += ch
    names = []
    for part in parts:
        match = _PARAM.match(part)
        if match:
            names.append(match.group(1))
    return names


def _callables_in(text):
    lines = text.splitlines()
    found = []
    in_block = False
    documenting = False
    for index, line in enumerate(lines):
        if line.strip().startswith("```"):
            documenting = not in_block and line.strip() == "```"
            in_block = not in_block
            continue
        if documenting:
            match = _CALL.match(line)
            if match:
                rest = "\n".join(lines[index:])[match.end():]
                found.append((match.group()[:-1], _params(rest)))
    return found


def _documented(comp_dir):
    found = []
    for name in ("library.md", "cli.md"):
        path = comp_dir / "interface" / name
        if path.exists():
            found.extend(_callables_in(path.read_text(encoding="utf-8")))
    return found


def _drift(code_dir, module_name, documented, repo_root):
    env = dict(os.environ)
    env["PYTHONPATH"] = str(code_dir)
    names = [name for name, _ in documented]
    proc = subprocess.run(
        [sys.executable, "-c", _DRIFT_SCRIPT, module_name, json.dumps(names)],
        cwd=str(repo_root), env=env, capture_output=True, text=True,
        stdin=subprocess.DEVNULL,
    )
    actual = json.loads(proc.stdout)
    return any(actual[name] != params for name, params in documented)


def _kill_tree(proc):
    listing = subprocess.run(["ps", "-eo", "pid=,ppid="], capture_output=True, text=True).stdout
    children = {}
    for line in listing.split("\n"):
        fields = line.split()
        if len(fields) == 2:
            children.setdefault(int(fields[1]), []).append(int(fields[0]))
    pending = [proc.pid]
    found = []
    while pending:
        for child in children.get(pending.pop(), []):
            found.append(child)
            pending.append(child)
    for pid in found:
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    proc.kill()


def _run(cmd, cwd, env):
    timeout = DEFAULT_TEST_TIMEOUT
    proc = subprocess.Popen(
        cmd, cwd=str(cwd), env=env, stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )
    try:
        output, _ = proc.communicate(timeout=timeout)
        return proc.returncode, output, False, timeout
    except subprocess.TimeoutExpired:
        _kill_tree(proc)
        output, _ = proc.communicate()
        return None, output, True, timeout


def _failure_message(rc, output, timed_out, timeout):
    if timed_out:
        return f"test timed out after {timeout} seconds"
    for line in output.splitlines():
        if line.startswith("FAILED ") and " - " in line:
            return line.split(" - ", 1)[1]
    return f"pytest exited with code {rc}"


def _literal(text):
    try:
        return ast.literal_eval(text)
    except Exception:
        return None


def _entry(crit):
    return {"id": crit["id"], "covers": crit["covers"], "kind": crit["kind"], "result": "pass"}


def _fail(entry, message, expected, actual, origin):
    entry["result"] = "fail"
    entry["failure_detail"] = {"message": message, "expected": expected, "actual": actual}
    entry["failure_origin"] = origin


def _judge(entry, component_id, repo_root, judge):
    entry["result"] = "skipped"
    entry["rationale"] = None
    if judge is not None:
        assembler = _load(repo_root, "gen/spec-bundle-assembler", "spec_bundle_assembler")
        bundle = assembler.assemble_criterion(component_id, entry["id"], repo_root)
        outcome = judge(bundle)
        if isinstance(outcome, dict):
            value = outcome.get("result", outcome.get("verdict"))
            entry["rationale"] = outcome.get("rationale")
        else:
            value = outcome
        entry["result"] = "pass" if value in (True, "pass") else "fail"


def _requirement_results(req_ids, entries):
    return {
        rid: "pass" if all(e["result"] == "pass" for e in entries if e["covers"] == rid) else "fail"
        for rid in req_ids
    }


def verify(component_id, repo_root, judge=None, test_author=None):
    repo_root = Path(repo_root).absolute()
    slug = component_id.removeprefix("comp-")
    comp_dir = repo_root / "specs" / "components" / slug
    frontmatter = _frontmatter((comp_dir / "component.md").read_text(encoding="utf-8"))
    criteria = _read_criteria(comp_dir)
    req_ids = sorted(p.stem for p in (comp_dir / "requirements").glob("*.md"))
    documented = _documented(comp_dir)
    module_name = slug.replace("-", "_")
    if frontmatter.get("sealed") == "true":
        return _verify_sealed(component_id, repo_root, slug, module_name, frontmatter["source_path"],
                              criteria, req_ids, documented, judge)
    return _verify_unsealed(component_id, repo_root, slug, module_name, criteria, req_ids,
                            documented, judge, test_author)


def _verify_sealed(component_id, repo_root, slug, module_name, source_path, criteria, req_ids,
                   documented, judge):
    code_dir = repo_root / source_path
    drift = _drift(code_dir, module_name, documented, repo_root)
    files = sorted((repo_root / "verification" / slug).glob("test_*.py"))
    defined = []
    for path in files:
        defined.extend(_TEST_DEF.findall(path.read_text(encoding="utf-8")))
    results = []
    tmp = Path(tempfile.mkdtemp(prefix="hotdocs-verify-"))
    try:
        if files:
            xml_path = tmp / "junit.xml"
            env = dict(os.environ)
            env["PYTHONPATH"] = str(code_dir)
            _run([sys.executable, "-m", "pytest", *[str(f) for f in files], f"--junitxml={xml_path}"],
                 repo_root, env)
            if xml_path.exists():
                for case in ET.parse(xml_path).iter("testcase"):
                    passed = not any(child.tag in ("failure", "error", "skipped") for child in case)
                    results.append((case.get("name").split("[")[0], passed))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    def matches(name, base):
        return name == base or name.startswith(base + "_")

    entries = []
    for crit in criteria:
        entry = _entry(crit)
        if crit["kind"] == "llm-judge":
            _judge(entry, component_id, repo_root, judge)
        else:
            base = "test_" + crit["id"].lower().replace("-", "_")
            exists = any(matches(name, base) for name in defined)
            outcomes = [passed for name, passed in results if matches(name, base)]
            if not (exists and outcomes and all(outcomes)):
                message = "characterization test failed" if exists else "no characterization test"
                _fail(entry, message, None, None, "implementation")
        entries.append(entry)
    failed = any(e["result"] == "fail" for e in entries)
    overall = "fail" if failed or drift or not code_dir.is_dir() else "pass"
    return VerificationReport(
        component_id=component_id,
        criteria=entries,
        requirement_results=_requirement_results(req_ids, entries),
        interface_drift=drift,
        mutation_score=None,
        mutation_error=None,
        assets=[],
        drivers=[],
        overall=overall,
    )


def _verify_unsealed(component_id, repo_root, slug, module_name, criteria, req_ids, documented,
                     judge, test_author):
    code_dir = repo_root / "gen" / slug
    run_environment = _load(repo_root, "gen/run-environment", "run_environment")
    environment = run_environment.prepare(component_id, repo_root)
    tmp = Path(tempfile.mkdtemp(prefix="hotdocs-verify-"))
    try:
        ok = _get(environment, "ok")
        entries = []
        passing = []
        mutation_score = None
        mutation_error = None
        compiled = {}
        if ok:
            interpreter = _get(environment, "interpreter")
            pytest_args = list(_get(environment, "pytest_args")())
            run_vars = dict(_get(environment, "env_for")(code_dir))
            run_vars["PYTHONPATH"] = os.pathsep.join([str(code_dir), str(_get(environment, "plugin_dir"))])
            asset_paths = [_get(a, "path") for a in list(_get(environment, "assets"))[1:]]
            driver_fixtures = list(_get(environment, "driver_fixtures")())
            if any(c["kind"] == "compiled" for c in criteria):
                compiler = _load(repo_root, "pipeline/criterion-compiler", "criterion_compiler")
                report = compiler.compile(component_id, repo_root, out_dir=tmp)
                for out in _get(report, "outputs"):
                    compiled[_get(out, "criterion_id")] = out
                (tmp / "conftest.py").write_text(_CONFTEST, encoding="utf-8")

        def pytest(file, extra):
            env = dict(os.environ)
            env.update(run_vars)
            env.update(extra)
            return _run([interpreter, "-m", "pytest", *pytest_args, str(file)], repo_root, env)

        for crit in criteria:
            entry = _entry(crit)
            if crit["kind"] == "llm-judge":
                _judge(entry, component_id, repo_root, judge)
            elif not ok:
                _fail(entry, _get(environment, "failure_message"), None, None, "environment")
            elif crit["kind"] == "compiled":
                out = compiled[crit["id"]]
                if _get(out, "status") != "compiled":
                    _fail(entry, _get(out, "message"), None, None, "test")
                else:
                    capture = tmp / f"capture_{crit['id']}.json"
                    rc, output, timed_out, timeout = pytest(
                        repo_root / _get(out, "file"), {"HOTDOCS_VO_CAPTURE": str(capture)})
                    if rc != 0:
                        data = json.loads(capture.read_text(encoding="utf-8")) if capture.exists() else {}
                        op, left, right = data.get("compare", ["==", "None", "None"])
                        expected, actual = (left, right) if op in ("in", "not in") else (right, left)
                        message = data.get("message") or _failure_message(rc, output, timed_out, timeout)
                        _fail(entry, message, _literal(expected), _literal(actual), "implementation")
            else:
                test_supply = _load(repo_root, "gen/test-supply", "test_supply")
                supplied = test_supply.supply(
                    component_id, crit["id"], repo_root, test_author=test_author,
                    interpreter=interpreter, assets=asset_paths, drivers=driver_fixtures,
                )
                authoring = _get(supplied, "test_authoring")
                if authoring is not None:
                    entry["test_authoring"] = authoring
                if _get(supplied, "failure_origin") == "test":
                    _fail(entry, _get(supplied, "failure_message"), None, None, "test")
                else:
                    path = str(_get(supplied, "path"))
                    rc, output, timed_out, timeout = pytest(path, {})
                    if rc == 0:
                        passing.append((path, entry))
                    else:
                        _fail(entry, _failure_message(rc, output, timed_out, timeout), None, None,
                              "implementation")
            entries.append(entry)

        if ok:
            scorer = _load(repo_root, "gen/mutation-scorer", "mutation_scorer")
            result = scorer.score(component_id, repo_root, [p for p, _ in passing], environment)
            mutation_score = _get(result, "mutation_score")
            mutation_error = _get(result, "mutation_error")
            faulty = list(_get(result, "faulty_tests"))
            for path, entry in passing:
                if path in faulty:
                    _fail(entry, "test fails in the mutation sandbox", None, None, "test")
                    test_supply = _load(repo_root, "gen/test-supply", "test_supply")
                    test_supply.discard(component_id, entry["id"], repo_root)

        drift = _drift(code_dir, module_name, documented, repo_root)
        bar = 0.9 if any(c["kind"] == "generated-test" and c["freeform"] for c in criteria) else 0.8
        failed = any(e["result"] == "fail" for e in entries)
        below = mutation_score is not None and mutation_score < bar
        overall = "fail" if failed or drift or mutation_error is not None or below else "pass"
        return VerificationReport(
            component_id=component_id,
            criteria=entries,
            requirement_results=_requirement_results(req_ids, entries),
            interface_drift=drift,
            mutation_score=mutation_score,
            mutation_error=mutation_error,
            assets=list(_get(environment, "assets")),
            drivers=list(_get(environment, "drivers")),
            overall=overall,
        )
    finally:
        _get(environment, "close")()
        shutil.rmtree(tmp, ignore_errors=True)


def _usage_error(cause):
    print(f"usage error: {cause}", file=sys.stderr)
    print(USAGE, file=sys.stderr)
    return 2


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    options = {"--repo-root": ".", "--format": "text"}
    positional = []
    index = 0
    while index < len(argv):
        token = argv[index]
        name, eq, value = token.partition("=")
        if name in options:
            if not eq:
                if index + 1 >= len(argv):
                    return _usage_error(f"{name} requires a value")
                index += 1
                value = argv[index]
            options[name] = value
        elif token.startswith("-") or positional:
            return _usage_error(f"unknown argument: {token}")
        else:
            positional.append(token)
        index += 1
    if not positional:
        return _usage_error("missing <component-id>")
    if options["--format"] not in ("json", "text"):
        return _usage_error(f"invalid --format: {options['--format']}")
    component_id = positional[0]
    repo_root = Path(options["--repo-root"])
    slug = component_id.removeprefix("comp-")
    if not (repo_root / "specs" / "components" / slug / "component.md").is_file():
        return _usage_error(f"unknown component: {component_id}")
    report = verify(component_id, repo_root)
    if options["--format"] == "json":
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print(f"{report.component_id}: {report.overall}")
        for entry in report.criteria:
            print(f"  {entry['id']}: {entry['result']}")
    return 0 if report.overall == "pass" else 1
