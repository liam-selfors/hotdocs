"""Verifier orchestrator: runs every verification gate against one component."""

import ast
import dataclasses
import hashlib
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
from dataclasses import dataclass, field
from pathlib import Path

GATE_VERSION = "verifier-orchestrator@3.5.0"
DEFAULT_TEST_TIMEOUT = 300.0

_USAGE = "usage: hotdocs verify-component <component-id> [--repo-root=<dir>] [--format=json|text]"
_HEADER_KEYS = ("criterion_text", "requirement_text", "interface", "glossary", "testing")
_TRANSIENT = ("network", "timeout", "rate_limit")
_AC_HEADING = re.compile(r"^#\s+(AC-[A-Z0-9-]*\d+[a-z]?)(?![\w-])", re.M)
_COVERS = re.compile(r"Covers:[*\s`]*([RP]-[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*)")
_KIND = re.compile(r"^[*\s]*Kind:[*\s`]*(compiled|generated-test|llm-judge)", re.M)
_JS = re.compile(r"\bfunction\s*[\w$]*\s*\(|=>|\b(const|let)\s")
_DRIFT_MARK = "HOTDOCS_DRIFT "

_PLUGIN = r'''import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest

_compare = []


@pytest.fixture
def asset_runner():
    entries = json.loads(os.environ.get("HOTDOCS_ASSETS", "[]"))

    def runner(path):
        for index, entry in enumerate(entries):
            if entry["path"] == path:
                name = "hotdocs_asset_adapter_%d" % index
                spec = importlib.util.spec_from_file_location(name, entry["adapter"])
                module = importlib.util.module_from_spec(spec)
                sys.modules[name] = module
                spec.loader.exec_module(module)
                return module.asset_runner(Path(entry["file"]))
        declared = ", ".join(entry["path"] for entry in entries) or "none"
        raise KeyError(
            "asset_runner: %r is not a declared asset (declared: %s)" % (path, declared))

    return runner


def pytest_runtest_logstart(nodeid, location):
    _compare.clear()


def pytest_assertrepr_compare(config, op, left, right):
    _compare[:] = [{"op": op, "left": repr(left), "right": repr(right)}]


def pytest_runtest_logreport(report):
    out = os.environ.get("HOTDOCS_RESULTS")
    if not out or (report.when != "call" and report.outcome == "passed"):
        return
    crash = getattr(report.longrepr, "reprcrash", None)
    lines = str(getattr(crash, "message", "")).splitlines()
    record = {"nodeid": report.nodeid, "outcome": report.outcome,
              "message": lines[0] if lines else "",
              "compare": _compare[0] if _compare else None}
    with open(out, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(record) + "\n")
'''

_DRIFT_SCRIPT = r'''import importlib
import inspect
import json
import sys

module = importlib.import_module(sys.argv[1])
found = {}
for name in json.loads(sys.argv[2]):
    obj = getattr(module, name, None)
    try:
        found[name] = list(inspect.signature(obj).parameters) if callable(obj) else None
    except (TypeError, ValueError):
        found[name] = None
print("HOTDOCS_DRIFT " + json.dumps(found))
'''


@dataclass
class VerificationReport:
    component_id: str
    criteria: list = field(default_factory=list)
    requirement_results: dict = field(default_factory=dict)
    interface_drift: bool = False
    mutation_score: object = None
    mutation_error: object = None
    assets: list = field(default_factory=list)
    overall: str = "fail"

    def to_dict(self):
        return dataclasses.asdict(self)


class _AdapterFailure(Exception):
    pass


def _get(obj, key, default=None):
    if isinstance(obj, Mapping):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _slug(component_id):
    return component_id.removeprefix("comp-")


def _read(path):
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def _tool_root():
    here = Path(__file__).resolve()
    return next((p.parent for p in here.parents if p.name == "gen"), here.parent)


def _frontmatter(text):
    match = re.match(r"---\n(.*?)\n---", text, re.S)
    return match.group(1).splitlines() if match else []


def _field(lines, key):
    return next((line.split(":", 1)[1].strip() for line in lines if line.startswith(key + ":")), None)


def _declared_assets(lines):
    value = _field(lines, "assets") or ""
    inner = value[value.find("[") + 1:value.rfind("]")]
    declared = []
    for item in inner.split(","):
        kind, _, path = item.strip().partition(":")
        if kind:
            declared.append((kind.strip(), path.strip()))
    return declared


def _criteria(spec_dir):
    found = []
    for path in sorted((spec_dir / "acceptance").glob("AC-*.md")):
        text = path.read_text(encoding="utf-8")
        heading = _AC_HEADING.search(text)
        if not heading:
            continue
        covers = _COVERS.search(text)
        kind = _KIND.search(text, covers.end())
        found.append({
            "id": heading.group(1),
            "covers": covers.group(1),
            "kind": kind.group(1) if kind else "compiled",
            "freeform": "```gherkin" not in text,
        })
    return found


def _param_names(inner):
    names, depth, part = [], 0, ""
    for ch in inner + ",":
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        if ch == "," and depth == 0:
            match = re.match(r"\s*\*{0,2}([A-Za-z_]\w*)", part)
            if match:
                names.append(match.group(1))
            part = ""
        else:
            part += ch
    return names


def _split_signature(text):
    name = re.match(r"\w+", text).group(0)
    depth = 0
    for index in range(len(name), len(text)):
        depth += {"(": 1, ")": -1}.get(text[index], 0)
        if depth == 0:
            break
    return name, _param_names(text[len(name) + 1:index])


def _block_signatures(text):
    found, block, buf = [], None, ""
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            block = stripped == "```" if block is None else None
            buf = ""
        elif block and (buf or re.match(r"\w+\(", line)):
            buf = (buf + " " + stripped).strip()
            if buf.count("(") <= buf.count(")"):
                found.append(_split_signature(buf))
                buf = ""
    return found


def _documented_callables(spec_dir):
    documented = {}
    for name, params in _block_signatures(_read(spec_dir / "interface" / "library.md")):
        documented.setdefault(name, params)
    cli = _read(spec_dir / "interface" / "cli.md")
    if cli:
        match = re.search(r"\bmain\(([^()]*)\)", cli)
        documented.setdefault("main", _param_names(match.group(1)) if match else None)
    return documented


def _kill_tree(pid):
    try:
        listing = subprocess.run(["ps", "-eo", "pid=,ppid="], capture_output=True, text=True).stdout
    except OSError:
        listing = ""
    children = {}
    for line in listing.splitlines():
        child, parent = line.split()
        children.setdefault(int(parent), []).append(int(child))
    stack, found = [pid], []
    while stack:
        for child in children.get(stack.pop(), []):
            found.append(child)
            stack.append(child)
    for child in found:
        try:
            os.kill(child, signal.SIGKILL)
        except OSError:
            pass


def _run(cmd, cwd, env, timeout, stdout=subprocess.DEVNULL):
    """Run cmd; return (exit code or None on timeout, elapsed seconds)."""
    start = time.monotonic()
    proc = subprocess.Popen(cmd, cwd=str(cwd), env=env, stdin=subprocess.DEVNULL,
                            stdout=stdout, stderr=subprocess.DEVNULL, start_new_session=True)
    try:
        code = proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        _kill_tree(proc.pid)
        proc.kill()
        proc.wait()
        return None, time.monotonic() - start
    return code, time.monotonic() - start


def _drift(code_dir, module_name, documented, interpreter):
    if not code_dir.is_dir():
        return True
    if not documented:
        return False
    env = dict(os.environ, PYTHONPATH=str(code_dir), PYTHONDONTWRITEBYTECODE="1")
    with tempfile.TemporaryFile() as out:
        _run([str(interpreter), "-c", _DRIFT_SCRIPT, module_name, json.dumps(list(documented))],
             code_dir, env, DEFAULT_TEST_TIMEOUT, out)
        out.seek(0)
        lines = out.read().decode("utf-8", "replace").splitlines()
    found = next((json.loads(line[len(_DRIFT_MARK):]) for line in reversed(lines)
                  if line.startswith(_DRIFT_MARK)), None)
    if found is None:
        return True
    return any(found.get(name) is None or (params is not None and found[name] != params)
               for name, params in documented.items())


def _hash_file(path):
    if path is None or not path.is_file():
        return None
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _adapter_path(repo_root, kind):
    rel = Path("gen") / f"kind-{kind}" / f"kind_{kind.replace('-', '_')}.py"
    return next((root / rel for root in (repo_root, _tool_root()) if (root / rel).is_file()), None)


def _test_filename(criterion_id):
    return "test_" + criterion_id.lower().replace("-", "_") + ".py"


def _first_line(path):
    return _read(path).split("\n", 1)[0].rstrip("\r")


def _header(bundle):
    payload = json.dumps({key: _get(bundle, key) for key in _HEADER_KEYS},
                         sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return "# hotdocs-criterion: sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _error_kinds(report):
    kinds = []
    for finding in _get(report, "findings") or []:
        kind = _get(finding, "kind")
        if _get(finding, "severity") == "error" and kind not in kinds:
            kinds.append(kind)
    return kinds


def _records(path):
    return [json.loads(line) for line in _read(path).splitlines() if line.strip()]


def _test_name(record):
    return record["nodeid"].split("::")[-1].split("[")[0]


def _literal(text):
    try:
        return ast.literal_eval(text)
    except (ValueError, SyntaxError, TypeError, MemoryError, RecursionError):
        return None


def _compared(compare):
    if not compare:
        return None, None
    left, right = _literal(compare["left"]), _literal(compare["right"])
    return (left, right) if compare["op"] in ("in", "not in") else (right, left)


def _detail(records, fallback):
    record = next((r for r in records if r["outcome"] != "passed"), {})
    expected, actual = _compared(record.get("compare"))
    return {"message": record.get("message") or fallback, "expected": expected, "actual": actual}


def _fail(entry, origin, message, expected=None, actual=None):
    entry["result"] = "fail"
    entry["failure_detail"] = {"message": message, "expected": expected, "actual": actual}
    entry["failure_origin"] = origin


def _adapter_call(kind, call):
    try:
        return call()
    except Exception as exc:
        raise _AdapterFailure(f"{kind} adapter failed: {type(exc).__name__}: {exc}") from exc


def _py_files(code_dir):
    files = [p for p in code_dir.rglob("*.py")
             if p.is_file() and "__pycache__" not in p.relative_to(code_dir).parts]
    return sorted(files, key=lambda p: p.relative_to(code_dir).as_posix())


def _find_javascript(code_dir):
    for path in _py_files(code_dir):
        try:
            tree = ast.parse(path.read_bytes())
        except (SyntaxError, ValueError):
            continue
        docstrings = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                for first in node.body[:1]:
                    if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
                        docstrings.add(id(first.value))
        for node in ast.walk(tree):
            if (isinstance(node, ast.Constant) and isinstance(node.value, str)
                    and id(node) not in docstrings and len(node.value) >= 200
                    and _JS.search(node.value) and (";" in node.value or "{" in node.value)):
                rel = path.relative_to(code_dir).as_posix()
                return (f"javascript in a string at {rel}:{node.lineno}; "
                        "declare it as an asset (specs/architecture/asset-kinds.md)")
    return None


def _baseline_error(code, timeout):
    if code is None:
        return f"mutation baseline timed out in the sandbox after {timeout:g} seconds"
    return f"mutation baseline failed in the sandbox: pytest exited {code}"


class _Verification:
    def __init__(self, component_id, repo_root, judge, test_author):
        self.component_id = component_id
        self.repo_root = Path(repo_root).resolve()
        self.judge = judge
        self.test_author = test_author
        self.slug = _slug(component_id)
        self.module_name = self.slug.replace("-", "_")
        self.spec_dir = self.repo_root / "specs" / "components" / self.slug
        self.modules = {}
        self.outputs = None
        self.counter = 0
        self.declared = []
        self.adapters = {}
        self.assets_env = []
        self.interp = sys.executable

    # -- loading -------------------------------------------------------
    def _load_file(self, path, module_name):
        key = (str(self.repo_root), module_name)
        if key not in self.modules:
            digest = hashlib.sha256(f"{self.repo_root}\0{path}".encode("utf-8")).hexdigest()[:16]
            name = f"_hotdocs_vo_{digest}_{module_name}"
            locations = [str(path.parent)] if path.name == "__init__.py" else None
            spec = importlib.util.spec_from_file_location(name, path, submodule_search_locations=locations)
            module = importlib.util.module_from_spec(spec)
            sys.modules[name] = module
            spec.loader.exec_module(module)
            self.modules[key] = module
        return self.modules[key]

    def _load_dependency(self, rel_dir, module_name):
        base = self.repo_root / rel_dir
        if not base.is_dir():
            base = _tool_root() / rel_dir
        path = base / f"{module_name}.py"
        if not path.is_file():
            path = base / module_name / "__init__.py"
        return self._load_file(path, module_name)

    def _bundle(self, criterion_id):
        assembler = self._load_dependency("gen/spec-bundle-assembler", "spec_bundle_assembler")
        return assembler.assemble_criterion(self.component_id, criterion_id, self.repo_root)

    # -- running -------------------------------------------------------
    def _results_file(self):
        self.counter += 1
        return self.work / f"results-{self.counter}.jsonl"

    def _pytest(self, files, cwd, code_dir, assets_env, timeout, extra=(), results=None):
        env = dict(os.environ)
        env.update({
            "PYTHONPATH": os.pathsep.join([str(code_dir), str(self.plug)]),
            "HOTDOCS_ASSETS": json.dumps(assets_env),
            "HOTDOCS_PYTHON": str(self.interp),
            "HOTDOCS_RESULTS": str(results or self._results_file()),
            "PYTHONDONTWRITEBYTECODE": "1",
        })
        cmd = [str(self.interp), "-m", "pytest", *[str(f) for f in files],
               "-p", "hotdocs_asset_runner", "-p", "no:cacheprovider", *extra]
        return _run(cmd, cwd, env, timeout)

    def _run_criterion(self, path):
        timeout = DEFAULT_TEST_TIMEOUT
        results = self._results_file()
        code, _ = self._pytest([path], self.repo_root, self.code_dir, self.assets_env, timeout,
                               results=results)
        if code == 0:
            return None
        if code is None:
            return {"message": f"test run timed out after {timeout:g} seconds",
                    "expected": None, "actual": None}
        return _detail(_records(results), f"pytest exited {code}")

    # -- criteria ------------------------------------------------------
    def _judge(self, entry):
        entry["result"] = "skipped"
        entry["rationale"] = None
        if self.judge is None:
            return
        outcome = self.judge(self._bundle(entry["id"]))
        value, rationale = outcome, None
        if not isinstance(outcome, (str, bool, int, float, type(None))):
            value = _get(outcome, "result", _get(outcome, "verdict"))
            rationale = _get(outcome, "rationale")
        entry["result"] = "pass" if value is True or value == "pass" else "fail"
        entry["rationale"] = rationale

    def _compiled(self, entry):
        if self.outputs is None:
            compiler = self._load_dependency("pipeline/criterion-compiler", "criterion_compiler")
            report = compiler.compile(self.component_id, self.repo_root)
            self.outputs = {_get(o, "criterion_id"): o for o in _get(report, "outputs") or []}
        output = self.outputs.get(entry["id"])
        if _get(output, "status") != "compiled":
            return _fail(entry, "implementation", _get(output, "message") or "criterion did not compile")
        detail = self._run_criterion(self.repo_root / Path(_get(output, "file")))
        if detail:
            return _fail(entry, "implementation", **detail)
        entry["result"] = "pass"

    def _author(self, bundle, entry):
        result = self.test_author(bundle)
        if _get(_get(result, "model_call_error"), "category") in _TRANSIENT:
            result = self.test_author(bundle)
        entry["test_authoring"] = {key: _get(result, key)
                                   for key in ("model", "seed", "prompt_version", "cache_hit")}
        error = _get(result, "model_call_error")
        if error is not None:
            return None, f"test authoring failed: {_get(error, 'category')}: {_get(error, 'message')}"
        path = self.work / _test_filename(entry["id"])
        path.write_text(_get(_get(result, "file"), "content") or "", encoding="utf-8")
        return path, None

    def _probe(self, path, bundle):
        probe = self._load_dependency("gen/test-probe", "test_probe").probe
        kwargs = {"interpreter": self.interp, "assets": [p for _, p in self.declared]}
        params = inspect.signature(probe).parameters
        if not any(p.kind is p.VAR_KEYWORD for p in params.values()):
            kwargs = {k: v for k, v in kwargs.items() if k in params}
        return probe(path.read_text(encoding="utf-8"), bundle, self.module_name, **kwargs)

    def _generated(self, entry, passing):
        bundle = self._bundle(entry["id"])
        cache = self.repo_root / "verification" / self.slug / "generated-test" / _test_filename(entry["id"])
        path, authored = None, False
        if _first_line(cache) == _header(bundle):
            path = cache
        if path is None:
            if self.test_author is None:
                return _fail(entry, "test", "no cached test and no test_author configured")
            path, error = self._author(bundle, entry)
            authored = True
            if error:
                return _fail(entry, "test", error)
        report = self._probe(path, bundle)
        if not _get(report, "ok") and not authored and self.test_author is not None:
            path, error = self._author(bundle, entry)
            if error:
                return _fail(entry, "test", error)
            report = self._probe(path, bundle)
        if not _get(report, "ok"):
            return _fail(entry, "test", "test failed its probe: " + ", ".join(_error_kinds(report)))
        detail = self._run_criterion(path)
        if detail:
            return _fail(entry, "implementation", **detail)
        entry["result"] = "pass"
        passing.append((entry, path, cache))

    # -- mutation ------------------------------------------------------
    def _mutation(self, passing):
        if not passing:
            return None, None
        sandbox = Path(tempfile.mkdtemp())
        try:
            gen = sandbox / "gen"
            gen.mkdir()
            code = gen / self.slug
            shutil.copytree(self.code_dir, code, ignore=shutil.ignore_patterns("__pycache__"))
            for directory in sorted((self.repo_root / "gen").iterdir()):
                if directory.is_dir() and directory.name != self.slug:
                    os.symlink(directory, gen / directory.name, target_is_directory=True)
            javascript = _find_javascript(code)
            if javascript:
                return None, javascript
            assets_env = [{"path": p, "file": str(code / p), "adapter": env["adapter"]}
                          for (_, p), env in zip(self.declared, self.assets_env)]

            def run(items, timeout):
                return self._pytest([item[1] for item in items], code, code, assets_env, timeout,
                                    extra=("--noconftest",))

            timeout = DEFAULT_TEST_TIMEOUT
            exit_code, elapsed = run(passing, timeout)
            if exit_code != 0:
                alone = [item for item in passing if run([item], timeout)[0] != 0]
                if not alone:
                    return None, _baseline_error(exit_code, timeout)
                for entry, _, cache in alone:
                    _fail(entry, "test", "test fails in the mutation sandbox")
                    cache.unlink(missing_ok=True)
                passing = [item for item in passing if item not in alone]
                if not passing:
                    return None, None
                exit_code, elapsed = run(passing, timeout)
                if exit_code != 0:
                    return None, _baseline_error(exit_code, timeout)
            mutant_timeout = max(2.0, 10 * elapsed)
            snapshot = {p: p.read_bytes() for p in code.rglob("*") if p.is_file()}
            targets = [("python", self.adapters["python"], code)] + [
                (kind, self.adapters[kind], code / path) for kind, path in self.declared]
            killed = total = 0
            try:
                for kind, adapter, target in targets:
                    sites = _adapter_call(kind, lambda: list(adapter.strength_sites(target)))
                    for site in sites:
                        _adapter_call(kind, lambda: adapter.apply_site(target, site))
                        total += 1
                        killed += run(passing, mutant_timeout)[0] != 0
                        for path, data in snapshot.items():
                            path.write_bytes(data)
            except _AdapterFailure as failure:
                return None, str(failure)
            return (killed / total if total else 1.0), None
        finally:
            shutil.rmtree(sandbox, ignore_errors=True)

    # -- component shapes ----------------------------------------------
    def _unsealed(self, criteria, frontmatter):
        self.code_dir = self.repo_root / "gen" / self.slug
        self.declared = _declared_assets(frontmatter)
        kinds = list(dict.fromkeys(["python"] + [kind for kind, _ in self.declared]))
        paths = {kind: _adapter_path(self.repo_root, kind) for kind in kinds}
        self.adapters = {kind: self._load_file(path, f"kind_{kind.replace('-', '_')}")
                         for kind, path in paths.items() if path is not None}
        reports = {kind: adapter.provision(self.repo_root) for kind, adapter in self.adapters.items()}
        env_error = None
        for kind in kinds:
            if kind not in reports:
                env_error = f"unknown asset kind: {kind}"
                break
            if not _get(reports[kind], "ok"):
                env_error = _get(reports[kind], "reason")
                break
        self.interp = _get(reports.get("python"), "interpreter")

        def asset(kind, path):
            report = reports.get(kind)
            return {
                "kind": kind,
                "path": path,
                "definition_sha256": _hash_file(
                    self.repo_root / "specs" / "architecture" / f"asset-kind-{kind}.md"),
                "adapter_sha256": _hash_file(paths[kind]),
                "versions": dict(_get(report, "versions") or {}),
                "lockfile_sha256": _get(report, "lockfile_sha256"),
            }

        assets = [asset("python", ".")] + [asset(kind, path) for kind, path in self.declared]
        self.assets_env = [{"path": path, "file": str(self.code_dir / path), "adapter": str(paths[kind])}
                           for kind, path in self.declared]
        entries, passing = [], []
        for crit in criteria:
            entry = {"id": crit["id"], "covers": crit["covers"], "kind": crit["kind"], "result": None}
            entries.append(entry)
            if crit["kind"] == "llm-judge":
                self._judge(entry)
            elif env_error is not None:
                _fail(entry, "environment", env_error)
            elif crit["kind"] == "generated-test":
                self._generated(entry, passing)
            else:
                self._compiled(entry)
        score, error = self._mutation(passing)
        drift = _drift(self.code_dir, self.module_name, _documented_callables(self.spec_dir),
                       self.interp or sys.executable)
        return entries, drift, assets, score, error

    def _sealed(self, criteria, source_path):
        self.interp = sys.executable
        self.code_dir = self.repo_root / source_path
        tests = sorted((self.repo_root / "verification" / self.slug).glob("test_*.py"))
        timeout = DEFAULT_TEST_TIMEOUT
        records, code = [], 0
        if tests:
            results = self._results_file()
            code, _ = self._pytest(tests, self.repo_root, self.code_dir, [], timeout, results=results)
            records = _records(results)
        entries = []
        for crit in criteria:
            entry = {"id": crit["id"], "covers": crit["covers"], "kind": crit["kind"], "result": None}
            entries.append(entry)
            if crit["kind"] == "llm-judge":
                self._judge(entry)
                continue
            prefix = "test_" + crit["id"].lower().replace("-", "_")
            mine = [r for r in records
                    if _test_name(r) == prefix or _test_name(r).startswith(prefix + "_")]
            if code is None:
                _fail(entry, "implementation", f"test run timed out after {timeout:g} seconds")
            elif not mine:
                _fail(entry, "implementation", "no characterization test")
            elif all(r["outcome"] == "passed" for r in mine):
                entry["result"] = "pass"
            else:
                _fail(entry, "implementation", **_detail(mine, f"pytest exited {code}"))
        drift = _drift(self.code_dir, self.module_name, _documented_callables(self.spec_dir),
                       sys.executable)
        return entries, drift, [], None, None

    def run(self):
        frontmatter = _frontmatter(_read(self.spec_dir / "component.md"))
        criteria = _criteria(self.spec_dir)
        self.plug = Path(tempfile.mkdtemp())
        self.work = Path(tempfile.mkdtemp())
        (self.plug / "hotdocs_asset_runner.py").write_text(_PLUGIN, encoding="utf-8")
        try:
            if _field(frontmatter, "sealed") == "true":
                entries, drift, assets, score, error = self._sealed(
                    criteria, _field(frontmatter, "source_path"))
            else:
                entries, drift, assets, score, error = self._unsealed(criteria, frontmatter)
        finally:
            shutil.rmtree(self.plug, ignore_errors=True)
            shutil.rmtree(self.work, ignore_errors=True)
        requirement_results = {}
        for rid in sorted(p.stem for p in (self.spec_dir / "requirements").glob("R-*.md")):
            covering = [e["result"] for e in entries if e["covers"] == rid]
            requirement_results[rid] = "pass" if all(r == "pass" for r in covering) else "fail"
        threshold = 0.9 if any(c["kind"] == "generated-test" and c["freeform"] for c in criteria) else 0.8
        failed = any(e["result"] == "fail" for e in entries)
        overall = "fail" if (failed or drift or error
                             or (score is not None and score < threshold)) else "pass"
        return VerificationReport(
            component_id=self.component_id,
            criteria=entries,
            requirement_results=requirement_results,
            interface_drift=drift,
            mutation_score=score,
            mutation_error=error,
            assets=assets,
            overall=overall,
        )


def verify(component_id, repo_root, judge=None, test_author=None):
    """Run every verification gate for one component and return its VerificationReport."""
    return _Verification(component_id, repo_root, judge, test_author).run()


def _usage(cause):
    print(f"usage error: {cause}", file=sys.stderr)
    print(_USAGE, file=sys.stderr)
    return 2


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    options = {"--repo-root": ".", "--format": "text"}
    component_id = None
    index = 0
    while index < len(args):
        token = args[index]
        name, equals, value = token.partition("=")
        if name in options:
            if not equals:
                if index + 1 == len(args):
                    return _usage(f"{name} needs a value")
                index += 1
                value = args[index]
            options[name] = value
        elif component_id is None and not token.startswith("-"):
            component_id = token
        else:
            return _usage(f"unknown argument: {token}")
        index += 1
    if component_id is None:
        return _usage("missing <component-id>")
    if options["--format"] not in ("json", "text"):
        return _usage(f"invalid --format: {options['--format']}")
    repo_root = Path(options["--repo-root"])
    if not (repo_root / "specs" / "components" / _slug(component_id) / "component.md").is_file():
        return _usage(f"unknown component: {component_id}")
    report = verify(component_id, repo_root)
    if options["--format"] == "json":
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print(f"{report.component_id}: {report.overall}")
        for criterion in report.criteria:
            print(f"  {criterion['id']}: {criterion['result']}")
    return 0 if report.overall == "pass" else 1
