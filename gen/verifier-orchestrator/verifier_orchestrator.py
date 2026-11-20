"""Verifier orchestrator: runs every verification gate against one component."""

import ast
import dataclasses
import hashlib
import importlib.util
import inspect
import itertools
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
from collections.abc import Mapping
from pathlib import Path

GATE_VERSION = "verifier-orchestrator@3.5.0"
DEFAULT_TEST_TIMEOUT = 300.0

USAGE = (
    "usage: hotdocs verify-component <component-id> "
    "[--repo-root=<dir>] [--format=json|text]"
)

_TRANSIENT = ("network", "timeout", "rate_limit")
_HEADER_KEYS = ("criterion_text", "requirement_text", "interface", "glossary", "testing")
_DEPENDENCIES = {
    "spec_bundle_assembler": "gen/spec-bundle-assembler",
    "test_probe": "gen/test-probe",
    "criterion_compiler": "pipeline/criterion-compiler",
}
_JS = re.compile(r"\bfunction\s*[\w$]*\s*\(|=>|\b(const|let)\s")
_LOADS = itertools.count()
_NO = object()

_PLUGIN_SOURCE = '''import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest


@pytest.fixture
def asset_runner():
    entries = json.loads(os.environ["HOTDOCS_ASSETS"])

    def runner(path):
        for entry in entries:
            if entry["path"] == path:
                name = "_hotdocs_asset_adapter_" + str(len(sys.modules))
                spec = importlib.util.spec_from_file_location(name, entry["adapter"])
                module = importlib.util.module_from_spec(spec)
                sys.modules[name] = module
                spec.loader.exec_module(module)
                return module.asset_runner(Path(entry["file"]))
        raise KeyError(path)

    return runner
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
    overall: str

    def to_dict(self):
        return dataclasses.asdict(self)


@dataclasses.dataclass
class _Criterion:
    id: str
    covers: str
    kind: str
    freeform: bool


# ---------------------------------------------------------------- helpers


def _get(obj, key, default=None):
    if isinstance(obj, Mapping):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _sha(path):
    return "sha256:" + hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _tool_root():
    here = Path(os.path.abspath(__file__))
    return next(p.parent for p in here.parents if p.name == "gen")


def _load_path(path, name, locations=None):
    load_name = f"_hotdocs_vo_{next(_LOADS)}_{name}"
    spec = importlib.util.spec_from_file_location(
        load_name, str(path), submodule_search_locations=locations
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[load_name] = module
    spec.loader.exec_module(module)
    return module


def _load_dir(directory, module_name):
    package = Path(directory) / module_name / "__init__.py"
    if package.is_file():
        return _load_path(package, module_name, [str(package.parent)])
    return _load_path(Path(directory) / f"{module_name}.py", module_name)


def _adapter_path(repo_root, kind):
    rel = Path("gen") / f"kind-{kind}" / f"kind_{kind}.py"
    path = repo_root / rel
    if not path.is_file():
        path = _tool_root() / rel
    return path if path.is_file() else None


def _test_stem(criterion_id):
    return "test_" + criterion_id.lower().replace("-", "_")


def _header(bundle):
    payload = json.dumps(
        {key: _get(bundle, key) for key in _HEADER_KEYS},
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return "# hotdocs-criterion: sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _detail(message, expected=None, actual=None):
    return {"message": message, "expected": expected, "actual": actual}


def _entry(crit, result, **extra):
    return {"id": crit.id, "covers": crit.covers, "kind": crit.kind, "result": result, **extra}


def _fail(crit, origin, detail, **extra):
    return _entry(crit, "fail", **extra, failure_origin=origin, failure_detail=detail)


def _error_kinds(report):
    kinds = []
    for finding in _get(report, "findings", []):
        kind = _get(finding, "kind")
        if _get(finding, "severity") == "error" and kind not in kinds:
            kinds.append(kind)
    return ", ".join(kinds)


# ---------------------------------------------------------------- spec parsing


def _frontmatter(text):
    match = re.match(r"---\s*\n(.*?)\n---", text, re.S)
    block = match.group(1) if match else ""
    sealed = re.search(r"^sealed:\s*true\s*$", block, re.M) is not None
    source = re.search(r"^source_path:\s*(.+?)\s*$", block, re.M)
    assets = re.search(r"^assets:[^\[\n]*\[(.*)\]", block, re.M)
    declared = []
    for item in assets.group(1).split(",") if assets else []:
        kind, _, path = item.strip().partition(":")
        if kind:
            declared.append((kind.strip(), path.strip()))
    return sealed, source.group(1) if source else None, declared


def _criteria(acceptance_dir):
    found = []
    for path in sorted(acceptance_dir.glob("AC-*.md")):
        text = path.read_text(encoding="utf-8")
        ident = re.search(r"^#\s+(AC-[A-Z0-9-]*[0-9][a-z]?)\b", text, re.M).group(1)
        covers = re.search(r"Covers:[\s*`]*([RP]-[A-Za-z0-9-]*[A-Za-z0-9])", text)
        kind = re.compile(r"^Kind:[ `]*(compiled|generated-test|llm-judge)", re.M).search(
            text, covers.end()
        ).group(1)
        gherkin = re.search(r"^\s*```gherkin", text, re.M) is not None
        found.append(
            _Criterion(ident, covers.group(1), kind, kind == "generated-test" and not gherkin)
        )
    return found


def _signatures(text):
    logical = []
    state = None
    buf = ""
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            state = None if state else ("plain" if stripped == "```" else "other")
            buf = ""
            continue
        if state != "plain":
            continue
        buf = f"{buf} {stripped}" if buf else line
        if buf.count("(") > buf.count(")"):
            continue
        logical.append(buf)
        buf = ""
    found = []
    for line in logical:
        match = re.match(r"(\w+)\(", line)
        if not match:
            continue
        depth = 0
        inside = ""
        for index in range(match.end() - 1, len(line)):
            depth += (line[index] in "([{") - (line[index] in ")]}")
            if depth == 0:
                inside = line[match.end():index]
                break
        found.append((match.group(1), _param_list(inside)))
    return found


def _param_list(inside):
    pieces = []
    depth = 0
    current = ""
    for char in inside:
        depth += (char in "([{") - (char in ")]}")
        if char == "," and depth == 0:
            pieces.append(current)
            current = ""
        else:
            current += char
    pieces.append(current)
    names = []
    for piece in pieces:
        match = re.match(r"\w+", piece.strip().lstrip("*"))
        if match:
            names.append(match.group(0))
    return names


def _interface_drift(interface_dir, code_dir, module_name):
    documented = []
    for name in ("library.md", "cli.md"):
        path = interface_dir / name
        if path.is_file():
            documented += _signatures(path.read_text(encoding="utf-8"))
    if (interface_dir / "cli.md").is_file():
        documented.append(("main", ["argv"]))
    try:
        module = _load_dir(code_dir, module_name)
    except Exception:
        return True
    for name, params in documented:
        obj = getattr(module, name, None)
        if not callable(obj) or list(inspect.signature(obj).parameters) != params:
            return True
    return False


def _characterization(test_dir):
    tests = []
    for path in sorted(test_dir.glob("test_*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        tests += [
            (path, node.name)
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
    return tests


def _py_files(directory):
    return sorted(
        (p for p in directory.rglob("*.py") if "__pycache__" not in p.relative_to(directory).parts),
        key=lambda p: p.relative_to(directory).as_posix(),
    )


def _javascript(copy):
    for path in _py_files(copy):
        tree = ast.parse(path.read_bytes())
        docs = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                for first in node.body[:1]:
                    if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
                        docs.add(id(first.value))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Constant)
                and isinstance(node.value, str)
                and id(node) not in docs
                and len(node.value) >= 200
                and _JS.search(node.value)
                and (";" in node.value or "{" in node.value)
            ):
                return f"{path.relative_to(copy).as_posix()}:{node.lineno}"
    return None


# ---------------------------------------------------------------- running


def _kill_tree(pid):
    listing = subprocess.run(["ps", "-eo", "pid=,ppid="], capture_output=True, text=True).stdout
    children = {}
    for line in listing.splitlines():
        fields = line.split()
        children.setdefault(int(fields[1]), []).append(int(fields[0]))
    stack, tree = [pid], []
    while stack:
        for child in children.get(stack.pop(), []):
            tree.append(child)
            stack.append(child)
    for target in tree + [pid]:
        try:
            os.kill(target, signal.SIGKILL)
        except OSError:
            pass


def _run(cmd, cwd, env, timeout):
    start = time.monotonic()
    proc = subprocess.Popen(
        cmd,
        cwd=str(cwd),
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        code = proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        _kill_tree(proc.pid)
        proc.wait()
        code = None
    return code, time.monotonic() - start


def _junit_failure(path):
    try:
        root = ET.parse(str(path)).getroot()
    except (OSError, ET.ParseError):
        return "", ""
    for case in root.iter("testcase"):
        for child in case:
            if child.tag in ("failure", "error"):
                return child.get("message", ""), child.text or ""
    return "", ""


def _literal(text, missing=None):
    try:
        return ast.literal_eval(text.strip())
    except (ValueError, SyntaxError, TypeError, MemoryError, RecursionError):
        return missing


def _rendered(rendered, sep, side):
    for match in re.finditer(re.escape(sep), rendered):
        sides = (
            _literal(rendered[: match.start()], _NO),
            _literal(rendered[match.end():], _NO),
        )
        if not any(value is _NO for value in sides):
            return sides[side]
    return None


def _compare(text):
    try:
        node = ast.parse(text, mode="eval").body
    except SyntaxError:
        return None
    if (
        isinstance(node, ast.Compare)
        and len(node.ops) == 1
        and isinstance(node.ops[0], (ast.Eq, ast.In))
    ):
        return node
    return None


def _pytest_detail(junit, code):
    if code is None:
        return _detail(f"test timed out after {DEFAULT_TEST_TIMEOUT:g} seconds")
    message, text = _junit_failure(junit)
    first = message.split("\n", 1)[0]
    source = re.search(r"^>\s+assert\s+(.+?)\s*$", text, re.M)
    node = _compare(source.group(1)) if source else None
    if node is not None:
        left = ast.unparse(node.left)
        right = ast.unparse(node.comparators[0])
        rendered = first[first.find("assert ") + len("assert "):]
        if isinstance(node.ops[0], ast.Eq):
            return _detail(
                f"{left} equals {right} failed", _literal(right), _rendered(rendered, " == ", 0)
            )
        return _detail(
            f"{right} contains {left} failed", _literal(left), _rendered(rendered, " in ", 1)
        )
    return _detail(first or f"pytest exited {code}")


# ---------------------------------------------------------------- orchestration


class _Verifier:
    def __init__(self, component_id, repo_root, judge, test_author, work):
        self.component_id = component_id
        self.repo_root = repo_root
        self.judge = judge
        self.test_author = test_author
        self.work = work
        self.slug = component_id.removeprefix("comp-")
        self.module_name = self.slug.replace("-", "_")
        self.spec_dir = repo_root / "specs" / "components" / self.slug
        self.plug = work / "plug"
        self.plug.mkdir()
        (self.plug / "hotdocs_asset_runner.py").write_text(_PLUGIN_SOURCE, encoding="utf-8")
        self.authored = work / "authored"
        self.authored.mkdir()
        self.compiled = None
        self.passing = []
        self.declared = []
        self.adapters = {}
        self.adapter_paths = {}
        self.interpreter = sys.executable
        self.code_dir = repo_root / "gen" / self.slug

    def dependency(self, name):
        rel = _DEPENDENCIES[name]
        base = self.repo_root / rel
        if not base.is_dir():
            base = _tool_root() / rel
        return _load_dir(base, name)

    def env(self, code_dir):
        env = dict(os.environ)
        env["PYTHONPATH"] = os.pathsep.join([str(code_dir), str(self.plug)])
        env["HOTDOCS_ASSETS"] = json.dumps(
            [
                {
                    "path": path,
                    "file": str(code_dir / path),
                    "adapter": str(self.adapter_paths[kind]),
                }
                for kind, path in self.declared
            ]
        )
        env["HOTDOCS_PYTHON"] = str(self.interpreter)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        return env

    def run(self):
        text = (self.spec_dir / "component.md").read_text(encoding="utf-8")
        sealed, source_path, declared = _frontmatter(text)
        criteria = _criteria(self.spec_dir / "acceptance")
        score = error = None
        if sealed:
            self.code_dir = self.repo_root / source_path
            assets, failure = [], None
            tests = _characterization(self.repo_root / "verification" / self.slug)
        else:
            self.declared = declared
            assets, failure = self.provision()
            tests = []
        drift = _interface_drift(self.spec_dir / "interface", self.code_dir, self.module_name)
        entries = []
        for crit in criteria:
            if crit.kind == "llm-judge":
                entries.append(self.judged(crit))
            elif sealed:
                entries.append(self.characterized(crit, tests))
            elif failure is not None:
                entries.append(_fail(crit, "environment", _detail(failure)))
            elif crit.kind == "compiled":
                entries.append(self.compiled_criterion(crit))
            else:
                entries.append(self.generated(crit))
        if not sealed and failure is None:
            score, error = self.mutation()
        results = {}
        for rid in sorted(p.stem for p in (self.spec_dir / "requirements").glob("R-*.md")):
            covering = [e["result"] for e in entries if e["covers"] == rid]
            results[rid] = "pass" if all(r == "pass" for r in covering) else "fail"
        threshold = 0.9 if any(c.freeform for c in criteria) else 0.8
        failed = (
            drift
            or error is not None
            or any(e["result"] == "fail" for e in entries)
            or (score is not None and score < threshold)
        )
        return VerificationReport(
            component_id=self.component_id,
            criteria=entries,
            requirement_results=results,
            interface_drift=drift,
            mutation_score=score,
            mutation_error=error,
            assets=assets,
            overall="fail" if failed else "pass",
        )

    # -- assets

    def provision(self):
        reports = {}
        failures = []
        for kind in ["python"] + [k for k, _ in self.declared]:
            if kind in reports:
                continue
            path = _adapter_path(self.repo_root, kind)
            self.adapter_paths[kind] = path
            report = {}
            if path is None:
                failures.append(f"unknown asset kind: {kind}")
            else:
                module = _load_path(path, f"kind_{kind}")
                self.adapters[kind] = module
                report = module.provision(self.repo_root)
                if not _get(report, "ok"):
                    failures.append(_get(report, "reason"))
            reports[kind] = report
        self.interpreter = _get(reports["python"], "interpreter")
        assets = [self.asset("python", ".", reports)] + [
            self.asset(kind, path, reports) for kind, path in self.declared
        ]
        return assets, failures[0] if failures else None

    def asset(self, kind, path, reports):
        definition = self.repo_root / "specs" / "architecture" / f"asset-kind-{kind}.md"
        adapter = self.adapter_paths[kind]
        return {
            "kind": kind,
            "path": path,
            "definition_sha256": _sha(definition) if definition.is_file() else None,
            "adapter_sha256": _sha(adapter) if adapter else None,
            "versions": _get(reports[kind], "versions", {}),
            "lockfile_sha256": _get(reports[kind], "lockfile_sha256"),
        }

    # -- criteria

    def bundle(self, crit):
        assembler = self.dependency("spec_bundle_assembler")
        return assembler.assemble_criterion(self.component_id, crit.id, self.repo_root)

    def judged(self, crit):
        if self.judge is None:
            return _entry(crit, "skipped", rationale=None)
        outcome = self.judge(self.bundle(crit))
        if isinstance(outcome, (str, bool)):
            result, rationale = outcome, None
        else:
            result = _get(outcome, "result", _get(outcome, "verdict"))
            rationale = _get(outcome, "rationale")
        return _entry(crit, "pass" if result in (True, "pass") else "fail", rationale=rationale)

    def run_criterion(self, crit, targets, extra):
        junit = self.work / f"{crit.id}.xml"
        cmd = [
            str(self.interpreter), "-m", "pytest", "-q",
            "-p", "no:cacheprovider", "-p", "hotdocs_asset_runner",
            f"--junitxml={junit}", *map(str, targets),
        ]
        code, _ = _run(cmd, self.repo_root, self.env(self.code_dir), DEFAULT_TEST_TIMEOUT)
        if code == 0:
            return _entry(crit, "pass", **extra)
        return _fail(crit, "implementation", _pytest_detail(junit, code), **extra)

    def characterized(self, crit, tests):
        stem = _test_stem(crit.id)
        targets = [
            f"{path}::{name}"
            for path, name in tests
            if name == stem or name.startswith(stem + "_")
        ]
        if not targets:
            return _fail(crit, "implementation", _detail("no characterization test"))
        return self.run_criterion(crit, targets, {})

    def compiled_criterion(self, crit):
        if self.compiled is None:
            compiler = self.dependency("criterion_compiler")
            report = compiler.compile(self.component_id, self.repo_root, out_dir=self.work / "compiled")
            self.compiled = {_get(o, "criterion_id"): o for o in _get(report, "outputs", [])}
        output = self.compiled.get(crit.id, {})
        if _get(output, "status") != "compiled":
            return _fail(crit, "implementation", _detail(_get(output, "message", "not compiled")))
        return self.run_criterion(crit, [self.repo_root / _get(output, "file")], {})

    def author(self, bundle, extra):
        outcome = self.test_author(bundle)
        if _get(_get(outcome, "model_call_error"), "category") in _TRANSIENT:
            outcome = self.test_author(bundle)
        extra["test_authoring"] = {
            key: _get(outcome, key) for key in ("model", "seed", "prompt_version", "cache_hit")
        }
        error = _get(outcome, "model_call_error")
        if error:
            return None, (
                f"test authoring failed: {_get(error, 'category')}: {_get(error, 'message')}"
            )
        return _get(_get(outcome, "file"), "content"), None

    def write(self, name, source):
        path = self.authored / name
        path.write_text(source, encoding="utf-8")
        return path

    def probe(self, source, bundle):
        probe = self.dependency("test_probe").probe
        kwargs = {}
        if "interpreter" in inspect.signature(probe).parameters:
            kwargs["interpreter"] = self.interpreter
        return probe(source, bundle, self.module_name, **kwargs)

    def generated(self, crit):
        bundle = self.bundle(crit)
        name = _test_stem(crit.id) + ".py"
        cache = self.repo_root / "verification" / self.slug / "generated-test" / name
        source = cache.read_text(encoding="utf-8") if cache.is_file() else ""
        extra = {}
        path, authored = cache, False
        if source.split("\n", 1)[0] != _header(bundle):
            if self.test_author is None:
                return _fail(
                    crit, "test", _detail("no current cached test and no test_author configured")
                )
            source, problem = self.author(bundle, extra)
            if problem:
                return _fail(crit, "test", _detail(problem), **extra)
            path, authored = self.write(name, source), True
        report = self.probe(source, bundle)
        if not _get(report, "ok") and not authored and self.test_author is not None:
            source, problem = self.author(bundle, extra)
            if problem:
                return _fail(crit, "test", _detail(problem), **extra)
            path = self.write(name, source)
            report = self.probe(source, bundle)
        if not _get(report, "ok"):
            return _fail(
                crit, "test", _detail("test failed its probe: " + _error_kinds(report)), **extra
            )
        entry = self.run_criterion(crit, [path], extra)
        if entry["result"] == "pass":
            self.passing.append((entry, path, cache))
        return entry

    # -- mutation

    def sandbox_run(self, copy, files, timeout):
        cmd = [
            str(self.interpreter), "-m", "pytest", "-q",
            "-p", "no:cacheprovider", "--noconftest", "-p", "hotdocs_asset_runner",
            *map(str, files),
        ]
        return _run(cmd, copy, self.env(copy), timeout)

    def mutation(self):
        if not self.passing:
            return None, None
        sandbox = self.work / "sandbox"
        copy = sandbox / "gen" / self.slug
        shutil.copytree(self.code_dir, copy, ignore=shutil.ignore_patterns("__pycache__"))
        for other in sorted((self.repo_root / "gen").iterdir()):
            if other.is_dir() and other.name != self.slug:
                os.symlink(other, sandbox / "gen" / other.name)
        found = _javascript(copy)
        if found:
            return None, (
                f"javascript in a string at {found}; declare it as an asset "
                "(specs/architecture/asset-kinds.md)"
            )
        tests = list(self.passing)
        code, elapsed = self.sandbox_run(copy, [t[1] for t in tests], DEFAULT_TEST_TIMEOUT)
        if code != 0:
            remaining = []
            for item in tests:
                alone, _ = self.sandbox_run(copy, [item[1]], DEFAULT_TEST_TIMEOUT)
                if alone != 0:
                    entry = item[0]
                    entry["result"] = "fail"
                    entry["failure_origin"] = "test"
                    entry["failure_detail"] = _detail("test fails in the mutation sandbox")
                    item[2].unlink(missing_ok=True)
                else:
                    remaining.append(item)
            if not remaining:
                return None, None
            if len(remaining) < len(tests):
                tests = remaining
                code, elapsed = self.sandbox_run(copy, [t[1] for t in tests], DEFAULT_TEST_TIMEOUT)
        if code is None:
            return None, "mutation baseline timed out in the sandbox after 300 seconds"
        if code != 0:
            return None, f"mutation baseline failed in the sandbox: pytest exited {code}"
        timeout = max(2.0, 10 * elapsed)
        files = [t[1] for t in tests]
        snapshot = {p: p.read_bytes() for p in copy.rglob("*") if p.is_file()}
        targets = [("python", copy)] + [(kind, copy / path) for kind, path in self.declared]
        killed = total = 0
        for kind, target in targets:
            adapter = self.adapters[kind]
            try:
                for site in adapter.strength_sites(target):
                    adapter.apply_site(target, site)
                    result, _ = self.sandbox_run(copy, files, timeout)
                    killed += result != 0
                    total += 1
                    for path, data in snapshot.items():
                        path.write_bytes(data)
            except Exception as exc:
                return None, f"{kind} adapter failed: {type(exc).__name__}: {exc}"
        return (killed / total if total else 1.0), None


def verify(component_id, repo_root, judge=None, test_author=None):
    with tempfile.TemporaryDirectory() as work:
        verifier = _Verifier(
            component_id, Path(repo_root).absolute(), judge, test_author, Path(work)
        )
        return verifier.run()


# ---------------------------------------------------------------- CLI


def _usage(cause):
    print(f"usage error: {cause}", file=sys.stderr)
    print(USAGE, file=sys.stderr)
    return 2


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    component_id = None
    repo_root = "."
    fmt = "text"
    index = 0
    while index < len(argv):
        token = argv[index]
        flag, eq, value = token.partition("=")
        if flag in ("--repo-root", "--format"):
            if not eq:
                if index + 1 >= len(argv):
                    return _usage(f"{flag} requires a value")
                index += 1
                value = argv[index]
            if flag == "--repo-root":
                repo_root = value
            else:
                fmt = value
        elif token.startswith("-") or component_id is not None:
            return _usage(f"unknown argument: {token}")
        else:
            component_id = token
        index += 1
    if component_id is None:
        return _usage("missing <component-id>")
    if fmt not in ("json", "text"):
        return _usage(f"invalid --format: {fmt}")
    root = Path(repo_root)
    slug = component_id.removeprefix("comp-")
    if not (root / "specs" / "components" / slug / "component.md").is_file():
        return _usage(f"unknown component: {component_id}")
    report = verify(component_id, root)
    if fmt == "json":
        print(json.dumps(report.to_dict(), indent=2, default=repr))
    else:
        print(f"{report.component_id}: {report.overall}")
        for criterion in report.criteria:
            print(f"  {criterion['id']}: {criterion['result']}")
    return 0 if report.overall == "pass" else 1
