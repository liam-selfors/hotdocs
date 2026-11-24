"""Verifier orchestrator: runs every verification gate for one component."""

from __future__ import annotations

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

USAGE = "usage: hotdocs verify-component <component-id> [--repo-root=<dir>] [--format=json|text]"

_RETRYABLE = ("network", "timeout", "rate_limit")
_BUNDLE_KEYS = ("criterion_text", "requirement_text", "interface", "glossary", "testing")
_JS_RE = re.compile(r"\bfunction\s*[\w$]*\s*\(|=>|\b(const|let)\s")
_ID_RE = re.compile(r"^# (AC-[A-Z0-9]+(?:-[A-Z0-9]+)*[a-z]?)", re.M)
_COVERS_RE = re.compile(r"Covers:[\s`@*]*([RP]-[A-Z0-9]+(?:-[A-Z0-9]+)*[a-z]?)")
_KIND_RE = re.compile(r"^Kind:\s*(compiled|generated-test|llm-judge)\s*$", re.M)
_GHERKIN_RE = re.compile(r"^\s*```gherkin\s*$", re.M)
_ASSERT_RE = re.compile(r"^E\s+assert (.+)$")
_COUNTER = itertools.count()

_PLUGIN = '''import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest


@pytest.fixture
def asset_runner():
    entries = json.loads(os.environ.get("HOTDOCS_ASSETS", "[]"))

    def runner(path):
        for index, entry in enumerate(entries):
            if entry["path"] == path:
                name = "hotdocs_asset_adapter_" + str(index)
                spec = importlib.util.spec_from_file_location(name, entry["adapter"])
                module = importlib.util.module_from_spec(spec)
                sys.modules[name] = module
                spec.loader.exec_module(module)
                return module.asset_runner(Path(entry["file"]))
        declared = ", ".join(e["path"] for e in entries) or "none"
        raise KeyError(
            f"asset_runner: {path!r} is not a declared asset (declared: {declared})")

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


def _get(obj, key, default=None):
    if isinstance(obj, Mapping):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _tool_root():
    here = Path(os.path.abspath(__file__))
    return next(p.parent for p in here.parents if p.name == "gen")


def _load_file(path, hint):
    name = f"_hotdocs_vo_{next(_COUNTER)}_{hint}"
    locations = [str(path.parent)] if path.name == "__init__.py" else None
    spec = importlib.util.spec_from_file_location(name, str(path), submodule_search_locations=locations)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _module_file(directory, module_name):
    flat = directory / f"{module_name}.py"
    if flat.is_file():
        return flat
    return directory / module_name / "__init__.py"


def _load_dependency(repo_root, rel, module_name):
    directory = repo_root / rel
    if not directory.is_dir():
        directory = _tool_root() / rel
    return _load_file(_module_file(directory, module_name), module_name)


def _adapter_path(repo_root, kind):
    rel = Path("gen") / f"kind-{kind}" / f"kind_{kind.replace('-', '_')}.py"
    for base in (repo_root, _tool_root()):
        if (base / rel).is_file():
            return base / rel
    return None


def _sha(path):
    if path is None or not Path(path).is_file():
        return None
    return "sha256:" + hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _frontmatter(path):
    fields = {}
    for line in path.read_text(encoding="utf-8").splitlines()[1:]:
        if line.strip() == "---":
            break
        key, sep, value = line.partition(":")
        if sep:
            fields.setdefault(key.strip(), value.strip())
    return fields


def _declared_assets(value):
    match = re.search(r"\[(.*)\]", value)
    if match is None:
        return []
    declared = []
    for item in match.group(1).split(","):
        item = item.strip()
        if item:
            kind, _, path = item.partition(":")
            declared.append((kind.strip(), path.strip()))
    return declared


def _criteria(acceptance_dir):
    found = []
    for path in sorted(acceptance_dir.glob("AC-*.md")):
        text = path.read_text(encoding="utf-8")
        covers = _COVERS_RE.search(text)
        kind = _KIND_RE.search(text, covers.end())
        found.append(_Criterion(
            id=_ID_RE.search(text).group(1),
            covers=covers.group(1),
            kind=kind.group(1) if kind else "compiled",
            freeform=_GHERKIN_RE.search(text) is None,
        ))
    return found


def _test_filename(criterion_id):
    return f"test_{criterion_id.lower().replace('-', '_')}.py"


def _header(bundle):
    data = {key: _get(bundle, key) for key in _BUNDLE_KEYS}
    text = json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return "# hotdocs-criterion: sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def _param_names(text):
    names, depth, piece = [], 0, ""
    for ch in text + ",":
        if ch == "," and depth == 0:
            match = re.match(r"\s*\*{0,2}([A-Za-z_]\w*)", piece)
            if match:
                names.append(match.group(1))
            piece = ""
            continue
        depth += ch in "([{"
        depth -= ch in ")]}"
        piece += ch
    return names


def _signatures(text):
    found = []
    for block in re.findall(r"^```[^\n]*\n(.*?)^```", text, re.M | re.S):
        for match in re.finditer(r"^(\w+)\(", block, re.M):
            depth = 0
            end = len(block)
            for j in range(match.end() - 1, len(block)):
                if block[j] in "([{":
                    depth += 1
                elif block[j] in ")]}":
                    depth -= 1
                    if depth == 0:
                        end = j
                        break
            found.append((match.group(1), _param_names(block[match.end():end])))
    return found


def _load_code(code_dir, module_name):
    path = _module_file(code_dir, module_name)
    if not path.is_file():
        return None
    sys.path.insert(0, str(code_dir))
    try:
        return _load_file(path, module_name)
    except Exception:
        return None
    finally:
        sys.path.remove(str(code_dir))


def _drift(comp_dir, code_dir, module_name):
    documented = []
    library = comp_dir / "interface" / "library.md"
    if library.is_file():
        documented += _signatures(library.read_text(encoding="utf-8"))
    cli = comp_dir / "interface" / "cli.md"
    if cli.is_file():
        text = cli.read_text(encoding="utf-8")
        documented += _signatures(text)
        match = re.search(r"\bmain\(([^()]*)\)", text)
        if match:
            documented.append(("main", _param_names(match.group(1))))
    module = _load_code(code_dir, module_name)
    if module is None:
        return True
    for name, params in documented:
        obj = getattr(module, name, None)
        if not callable(obj):
            return True
        try:
            actual = [p.name for p in inspect.signature(obj).parameters.values()]
        except (TypeError, ValueError):
            return True
        if actual != params:
            return True
    return False


def _descendants(pid):
    out = subprocess.run(["ps", "-eo", "pid=,ppid="], capture_output=True, text=True).stdout
    children = {}
    for line in out.splitlines():
        parts = line.split()
        if len(parts) == 2:
            children.setdefault(int(parts[1]), []).append(int(parts[0]))
    found, stack = [], [pid]
    while stack:
        for child in children.get(stack.pop(), []):
            found.append(child)
            stack.append(child)
    return found


def _run(cmd, cwd, env, timeout):
    start = time.monotonic()
    proc = subprocess.Popen(cmd, cwd=str(cwd), env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    try:
        out, _ = proc.communicate(timeout=timeout)
        code = proc.returncode
    except subprocess.TimeoutExpired:
        for pid in _descendants(proc.pid):
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass
        proc.kill()
        out, _ = proc.communicate()
        code = None
    return code, out.decode("utf-8", "replace"), time.monotonic() - start


def _compared(expr):
    for op in (" == ", " in "):
        start = expr.find(op)
        while start != -1:
            left, right = expr[:start], expr[start + len(op):]
            try:
                left_value, right_value = ast.literal_eval(left), ast.literal_eval(right)
            except (ValueError, SyntaxError, TypeError, MemoryError, RecursionError):
                start = expr.find(op, start + 1)
                continue
            if op == " == ":
                return right_value, left_value
            return left_value, right_value
    return None, None


def _failure_from_output(code, output, timeout):
    if code is None:
        return {"message": f"timed out after {timeout:g} seconds", "expected": None, "actual": None}
    source = None
    for line in output.splitlines():
        if line.startswith(">"):
            source = line[1:].strip()
        match = _ASSERT_RE.match(line)
        if match:
            expected, actual = _compared(match.group(1))
            return {"message": f"{source or 'assert ' + match.group(1)} failed",
                    "expected": expected, "actual": actual}
    return {"message": f"pytest exited {code}", "expected": None, "actual": None}


def _fail(entry, origin, message):
    entry["result"] = "fail"
    entry["failure_origin"] = origin
    entry["failure_detail"] = {"message": message, "expected": None, "actual": None}


def _py_files(code_dir):
    files = [p for p in code_dir.rglob("*.py") if "__pycache__" not in p.relative_to(code_dir).parts]
    return sorted(((p.relative_to(code_dir).as_posix(), p) for p in files), key=lambda t: t[0])


def _javascript_site(code_dir):
    for rel, path in _py_files(code_dir):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        docs = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                body = node.body
                if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                    docs.add(id(body[0].value))
        for node in ast.walk(tree):
            if (isinstance(node, ast.Constant) and isinstance(node.value, str)
                    and id(node) not in docs and len(node.value) >= 200
                    and _JS_RE.search(node.value)
                    and (";" in node.value or "{" in node.value)):
                return f"{rel}:{node.lineno}"
    return None


def _junit(path):
    outcomes = {}
    for case in ET.parse(path).getroot().iter("testcase"):
        bad = next((c for c in case if c.tag in ("failure", "error", "skipped")), None)
        outcomes.setdefault(case.get("name", "").split("[")[0], []).append(bad)
    return outcomes


def _baseline_error(code):
    if code is None:
        return "mutation baseline timed out in the sandbox after 300 seconds"
    return f"mutation baseline failed in the sandbox: pytest exited {code}"


class _Verification:
    def __init__(self, component_id, repo_root, judge, test_author, work):
        self.component_id = component_id
        self.repo_root = repo_root
        self.judge = judge
        self.test_author = test_author
        self.work = work
        self.slug = component_id.removeprefix("comp-")
        self.module_name = self.slug.replace("-", "_")
        self.comp_dir = repo_root / "specs" / "components" / self.slug
        self.front = _frontmatter(self.comp_dir / "component.md")
        self.criteria = _criteria(self.comp_dir / "acceptance")
        self.requirements = sorted(p.stem for p in (self.comp_dir / "requirements").glob("R-*.md"))
        self.plug = work / "plug"
        self.plug.mkdir()
        (self.plug / "hotdocs_asset_runner.py").write_text(_PLUGIN, encoding="utf-8")
        self.authored_dir = work / "authored"
        self.authored_dir.mkdir()
        self.declared = []
        self.info = {}
        self.interpreter = sys.executable
        self.env_error = None
        self.passing = []
        self._assembler = None
        self._probe = None
        self._compiled = None

    # -- dependencies -------------------------------------------------
    def bundle(self, crit):
        if self._assembler is None:
            self._assembler = _load_dependency(
                self.repo_root, Path("gen") / "spec-bundle-assembler", "spec_bundle_assembler")
        return self._assembler.assemble_criterion(self.component_id, crit.id, self.repo_root)

    def probe(self, source, bundle):
        if self._probe is None:
            self._probe = _load_dependency(self.repo_root, Path("gen") / "test-probe", "test_probe")
        func = self._probe.probe
        kwargs = {"interpreter": str(self.interpreter), "assets": [p for _, p in self.declared]}
        params = inspect.signature(func).parameters
        if not any(p.kind is inspect.Parameter.VAR_KEYWORD for p in params.values()):
            kwargs = {k: v for k, v in kwargs.items() if k in params}
        return func(source, bundle, self.module_name, **kwargs)

    # -- running ------------------------------------------------------
    def pytest(self, files, cwd, code_dir, timeout, extra=()):
        env = dict(os.environ)
        env["PYTHONPATH"] = os.pathsep.join((str(code_dir), str(self.plug)))
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env["HOTDOCS_ASSETS"] = json.dumps([
            {"path": path, "file": str(code_dir / path), "adapter": str(self.info[kind][0])}
            for kind, path in self.declared
        ])
        cmd = [str(self.interpreter), "-m", "pytest", *extra, "-p", "hotdocs_asset_runner",
               *[str(f) for f in files]]
        return _run(cmd, cwd, env, timeout)

    def run_criterion(self, entry, path):
        timeout = DEFAULT_TEST_TIMEOUT
        code, output, _ = self.pytest([path], self.repo_root, self.repo_root / "gen" / self.slug,
                                      timeout, extra=("-vv",))
        if code == 0:
            entry["result"] = "pass"
            return True
        entry["result"] = "fail"
        entry["failure_origin"] = "implementation"
        entry["failure_detail"] = _failure_from_output(code, output, timeout)
        return False

    # -- kinds --------------------------------------------------------
    def judge_entry(self, crit, entry):
        entry["rationale"] = None
        if self.judge is None:
            entry["result"] = "skipped"
            return
        outcome = self.judge(self.bundle(crit))
        value = _get(outcome, "result")
        if value is None:
            value = _get(outcome, "verdict")
        if value is None:
            value = outcome
        entry["result"] = "pass" if value is True or value == "pass" else "fail"
        entry["rationale"] = _get(outcome, "rationale")

    def compiled(self, crit, entry):
        if self._compiled is None:
            compiler = _load_dependency(
                self.repo_root, Path("pipeline") / "criterion-compiler", "criterion_compiler")
            report = compiler.compile(self.component_id, self.repo_root)
            self._compiled = {_get(o, "criterion_id"): o for o in _get(report, "outputs", [])}
        output = self._compiled.get(crit.id)
        if _get(output, "status") != "compiled":
            _fail(entry, "implementation", _get(output, "message") or "criterion was not compiled")
            return
        self.run_criterion(entry, self.repo_root / _get(output, "file"))

    def author(self, bundle, entry, filename):
        result = self.test_author(bundle)
        error = _get(result, "model_call_error")
        if error is not None and _get(error, "category") in _RETRYABLE:
            result = self.test_author(bundle)
            error = _get(result, "model_call_error")
        entry["test_authoring"] = {
            "model": _get(result, "model"),
            "seed": _get(result, "seed"),
            "prompt_version": _get(result, "prompt_version"),
            "cache_hit": _get(result, "cache_hit"),
        }
        if error is not None:
            return None, f"test authoring failed: {_get(error, 'category')}: {_get(error, 'message')}"
        content = _get(_get(result, "file"), "content")
        (self.authored_dir / filename).write_text(content, encoding="utf-8")
        return content, None

    def generated(self, crit, entry):
        bundle = self.bundle(crit)
        filename = _test_filename(crit.id)
        cache = self.repo_root / "verification" / self.slug / "generated-test" / filename
        source, path, authored = None, cache, False
        if cache.is_file():
            text = cache.read_text(encoding="utf-8")
            if (text.splitlines() or [""])[0] == _header(bundle):
                source = text
        if source is None:
            if self.test_author is None:
                _fail(entry, "test", "no cached test and no test_author configured")
                return
            source, problem = self.author(bundle, entry, filename)
            if problem is not None:
                _fail(entry, "test", problem)
                return
            authored, path = True, self.authored_dir / filename
        report = self.probe(source, bundle)
        if not _get(report, "ok") and not authored and self.test_author is not None:
            source, problem = self.author(bundle, entry, filename)
            if problem is not None:
                _fail(entry, "test", problem)
                return
            path = self.authored_dir / filename
            report = self.probe(source, bundle)
        if not _get(report, "ok"):
            kinds = []
            for finding in _get(report, "findings", []):
                kind = _get(finding, "kind")
                if _get(finding, "severity") == "error" and kind not in kinds:
                    kinds.append(kind)
            _fail(entry, "test", "test failed its probe: " + ", ".join(kinds))
            return
        if self.run_criterion(entry, path):
            self.passing.append((entry, path, cache))

    # -- assets -------------------------------------------------------
    def provision(self):
        self.declared = _declared_assets(self.front.get("assets", ""))
        for kind in ["python"] + [k for k, _ in self.declared]:
            if kind in self.info:
                continue
            path = _adapter_path(self.repo_root, kind)
            module = _load_file(path, f"kind_{kind.replace('-', '_')}") if path else None
            report = module.provision(self.repo_root) if module else None
            self.info[kind] = (path, module, report)
        for kind, (_, module, report) in self.info.items():
            if module is None:
                self.env_error = f"unknown asset kind: {kind}"
                break
            if not _get(report, "ok"):
                self.env_error = str(_get(report, "reason"))
                break
        self.interpreter = _get(self.info["python"][2], "interpreter")

    def asset_entries(self):
        entries = []
        for kind, path in [("python", ".")] + self.declared:
            adapter_path, _, report = self.info[kind]
            entries.append({
                "kind": kind,
                "path": path,
                "definition_sha256": _sha(self.repo_root / "specs" / "architecture" / f"asset-kind-{kind}.md"),
                "adapter_sha256": _sha(adapter_path),
                "versions": _get(report, "versions", {}),
                "lockfile_sha256": _get(report, "lockfile_sha256"),
            })
        return entries

    # -- mutation -----------------------------------------------------
    def mutation(self):
        runs = list(self.passing)
        if not runs:
            return None, None
        sandbox_gen = self.work / "sandbox" / "gen"
        copy = sandbox_gen / self.slug
        shutil.copytree(self.repo_root / "gen" / self.slug, copy,
                        ignore=shutil.ignore_patterns("__pycache__"))
        for directory in sorted((self.repo_root / "gen").iterdir()):
            if directory.is_dir() and directory.name != self.slug:
                (sandbox_gen / directory.name).symlink_to(directory)
        site = _javascript_site(copy)
        if site is not None:
            return None, (f"javascript in a string at {site}; declare it as an asset "
                          "(specs/architecture/asset-kinds.md)")

        def sandbox_run(files, timeout):
            code, _, elapsed = self.pytest(files, copy, copy, timeout, extra=("--noconftest",))
            return code, elapsed

        code, elapsed = sandbox_run([f for _, f, _ in runs], DEFAULT_TEST_TIMEOUT)
        if code != 0:
            faulty = [run for run in runs if sandbox_run([run[1]], DEFAULT_TEST_TIMEOUT)[0] != 0]
            if not faulty:
                return None, _baseline_error(code)
            for entry, _, cache in faulty:
                _fail(entry, "test", "test fails in the mutation sandbox")
                cache.unlink(missing_ok=True)
            runs = [run for run in runs if run not in faulty]
            if not runs:
                return None, None
            code, elapsed = sandbox_run([f for _, f, _ in runs], DEFAULT_TEST_TIMEOUT)
            if code != 0:
                return None, _baseline_error(code)
        mutant_timeout = max(2.0, 10 * elapsed)
        files = [f for _, f, _ in runs]
        snapshot = {p: p.read_bytes() for p in copy.rglob("*") if p.is_file()}
        targets = [("python", copy)] + [(kind, copy / path) for kind, path in self.declared]
        killed = total = 0
        for kind, target in targets:
            adapter = self.info[kind][1]
            try:
                sites = list(adapter.strength_sites(target))
            except Exception as exc:
                return None, f"{kind} adapter failed: {type(exc).__name__}: {exc}"
            for site_info in sites:
                try:
                    adapter.apply_site(target, site_info)
                except Exception as exc:
                    return None, f"{kind} adapter failed: {type(exc).__name__}: {exc}"
                code, _ = sandbox_run(files, mutant_timeout)
                total += 1
                killed += code != 0
                for path, data in snapshot.items():
                    path.write_bytes(data)
        return (killed / total if total else 1.0), None

    # -- top level ----------------------------------------------------
    def entry_for(self, crit):
        return {"id": crit.id, "covers": crit.covers, "kind": crit.kind, "result": None}

    def requirement_results(self, entries):
        return {
            rid: "pass" if all(e["result"] == "pass" for e in entries if e["covers"] == rid) else "fail"
            for rid in self.requirements
        }

    def unsealed(self):
        self.provision()
        drift = _drift(self.comp_dir, self.repo_root / "gen" / self.slug, self.module_name)
        entries = []
        for crit in self.criteria:
            entry = self.entry_for(crit)
            entries.append(entry)
            if crit.kind == "llm-judge":
                self.judge_entry(crit, entry)
            elif self.env_error is not None:
                _fail(entry, "environment", self.env_error)
            elif crit.kind == "compiled":
                self.compiled(crit, entry)
            else:
                self.generated(crit, entry)
        score = error = None
        if self.env_error is None:
            score, error = self.mutation()
        freeform = any(c.freeform for c in self.criteria if c.kind == "generated-test")
        threshold = 0.9 if freeform else 0.8
        failed = any(e["result"] == "fail" for e in entries)
        below = score is not None and score < threshold
        overall = "fail" if failed or drift or error is not None or below else "pass"
        return VerificationReport(
            component_id=self.component_id,
            criteria=entries,
            requirement_results=self.requirement_results(entries),
            interface_drift=drift,
            mutation_score=score,
            mutation_error=error,
            assets=self.asset_entries(),
            overall=overall,
        )

    def sealed(self):
        code_dir = self.repo_root / self.front.get("source_path", "")
        drift = _drift(self.comp_dir, code_dir, self.module_name)
        files = sorted((self.repo_root / "verification" / self.slug).glob("test_*.py"))
        names = set()
        for path in files:
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test"):
                    names.add(node.name)
        outcomes, code = {}, 0
        timeout = DEFAULT_TEST_TIMEOUT
        if files:
            xml = self.work / "sealed.xml"
            code, _, _ = self.pytest(files, self.repo_root, code_dir, timeout,
                                     extra=(f"--junitxml={xml}",))
            if xml.is_file():
                outcomes = _junit(xml)
        entries = []
        for crit in self.criteria:
            entry = self.entry_for(crit)
            entries.append(entry)
            if crit.kind == "llm-judge":
                self.judge_entry(crit, entry)
                continue
            prefix = "test_" + crit.id.lower().replace("-", "_")
            matched = sorted(n for n in names if n == prefix or n.startswith(prefix + "_"))
            if not matched:
                _fail(entry, "implementation", "no characterization test")
                continue
            problems = [b for n in matched for b in outcomes.get(n, ["missing"]) if b is not None]
            if not problems:
                entry["result"] = "pass"
                continue
            first = problems[0]
            entry["result"] = "fail"
            entry["failure_origin"] = "implementation"
            if code is None:
                entry["failure_detail"] = _failure_from_output(None, "", timeout)
            elif isinstance(first, str):
                entry["failure_detail"] = {"message": "characterization test did not run",
                                           "expected": None, "actual": None}
            else:
                text = (first.get("message") or "") + "\n" + (first.text or "")
                entry["failure_detail"] = _failure_from_output(1, text, timeout)
        failed = any(e["result"] == "fail" for e in entries)
        return VerificationReport(
            component_id=self.component_id,
            criteria=entries,
            requirement_results=self.requirement_results(entries),
            interface_drift=drift,
            mutation_score=None,
            mutation_error=None,
            assets=[],
            overall="fail" if failed or drift else "pass",
        )


def verify(component_id: str, repo_root: Path, judge=None, test_author=None) -> VerificationReport:
    repo_root = Path(os.path.abspath(repo_root))
    with tempfile.TemporaryDirectory() as work:
        run = _Verification(component_id, repo_root, judge, test_author, Path(work))
        if run.front.get("sealed") == "true":
            return run.sealed()
        return run.unsealed()


def _usage(cause):
    print(f"usage error: {cause}", file=sys.stderr)
    print(USAGE, file=sys.stderr)
    return 2


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    options = {"--repo-root": ".", "--format": "text"}
    component_id = None
    i = 0
    while i < len(args):
        token = args[i]
        name, sep, value = token.partition("=")
        if name in options:
            if not sep:
                if i + 1 >= len(args):
                    return _usage(f"{name} needs a value")
                i += 1
                value = args[i]
            options[name] = value
        elif token.startswith("-") or component_id is not None:
            return _usage(f"unknown argument: {token}")
        else:
            component_id = token
        i += 1
    if component_id is None:
        return _usage("missing <component-id>")
    if options["--format"] not in ("json", "text"):
        return _usage(f"invalid --format: {options['--format']}")
    repo_root = Path(options["--repo-root"])
    slug = component_id.removeprefix("comp-")
    if not (repo_root / "specs" / "components" / slug / "component.md").is_file():
        return _usage(f"no specs/components/{slug}/component.md")
    report = verify(component_id, repo_root)
    if options["--format"] == "json":
        print(json.dumps(report.to_dict(), indent=2, default=str))
    else:
        print(f"{report.component_id}: {report.overall}")
        for entry in report.criteria:
            print(f"  {entry['id']}: {entry['result']}")
    return 0 if report.overall == "pass" else 1
