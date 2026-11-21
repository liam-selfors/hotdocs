"""Verifier orchestrator: runs every verification gate against one component."""

from __future__ import annotations

import ast
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

USAGE = (
    "usage: hotdocs verify-component <component-id> "
    "[--repo-root=<dir>] [--format=json|text]"
)

_RETRY_CATEGORIES = ("network", "timeout", "rate_limit")
_HEADER_KEYS = ("criterion_text", "requirement_text", "interface", "glossary", "testing")
_HEADER_PREFIX = "# hotdocs-criterion: sha256:"
_JS_RE = re.compile(r"\bfunction\s*[\w$]*\s*\(|=>|\b(const|let)\s")
_HEADING_RE = re.compile(r"(?m)^#\s+(AC-[A-Z0-9]+(?:-[A-Z0-9]+)*[a-z]?)")
_COVERS_RE = re.compile(r"Covers:[*_`\s]*([RP]-[A-Za-z0-9-]+)")
_KIND_RE = re.compile(r"(?m)^[*_`\s]*Kind:[*_`\s]*(compiled|generated-test|llm-judge)\b")
_GHERKIN_RE = re.compile(r"(?m)^\s*```gherkin\s*$")
_BLOCK_RE = re.compile(r"(?ms)^```[^\n]*\n(.*?)^```")

_PLUGIN_SOURCE = '''import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest


@pytest.fixture
def asset_runner():
    entries = json.loads(os.environ.get("HOTDOCS_ASSETS", "[]"))

    def runner(path):
        for entry in entries:
            if entry["path"] == path:
                name = "hotdocs_asset_adapter_" + str(abs(hash(entry["adapter"])))
                spec = importlib.util.spec_from_file_location(name, entry["adapter"])
                module = importlib.util.module_from_spec(spec)
                sys.modules[name] = module
                spec.loader.exec_module(module)
                return module.asset_runner(Path(entry["file"]))
        raise KeyError(path)

    return runner


def pytest_assertrepr_compare(config, op, left, right):
    target = os.environ.get("HOTDOCS_FAILURE_RECORD")
    if target:
        with open(target, "a", encoding="utf-8") as handle:
            handle.write(json.dumps({"op": op, "left": repr(left), "right": repr(right)}) + "\\n")
    return None
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
    overall: str = "pass"

    def to_dict(self):
        return {
            "component_id": self.component_id,
            "criteria": [dict(c) for c in self.criteria],
            "requirement_results": dict(self.requirement_results),
            "interface_drift": self.interface_drift,
            "mutation_score": self.mutation_score,
            "mutation_error": self.mutation_error,
            "assets": [dict(a) for a in self.assets],
            "overall": self.overall,
        }


# ---------------------------------------------------------------- helpers


def _get(obj, key, default=None):
    if isinstance(obj, Mapping):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _slug(component_id):
    return component_id.removeprefix("comp-")


def _tool_root():
    here = Path(__file__).absolute()
    return next(parent.parent for parent in here.parents if parent.name == "gen")


def _sha256_file(path):
    return "sha256:" + hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _load_path(path, label):
    path = Path(path).absolute()
    name = "_hotdocs_vo_" + hashlib.sha256(str(path).encode("utf-8")).hexdigest()[:16] + "_" + label
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _test_filename(criterion_id):
    return "test_" + criterion_id.lower().replace("-", "_") + ".py"


def _literal(text):
    try:
        return ast.literal_eval(text)
    except (ValueError, SyntaxError):
        return None


def _header(bundle):
    payload = json.dumps(
        {k: _get(bundle, k) for k in _HEADER_KEYS},
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return _HEADER_PREFIX + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _frontmatter(text):
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return []
    out = []
    for line in lines[1:]:
        if line.strip() == "---":
            break
        out.append(line)
    return out


def _component_meta(text):
    sealed = False
    source_path = None
    assets = []
    for line in _frontmatter(text):
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        if key == "sealed":
            sealed = value == "true"
        elif key == "source_path":
            source_path = value
        elif line.startswith("assets:"):
            inner = value[value.find("[") + 1:value.rfind("]")]
            for item in inner.split(","):
                item = item.strip()
                if item:
                    kind, _, path = item.partition(":")
                    assets.append((kind.strip(), path.strip()))
    return sealed, source_path, assets


@dataclass
class _Criterion:
    id: str
    covers: object
    kind: str
    freeform: bool


def _criteria(spec_dir):
    found = []
    for path in sorted((spec_dir / "acceptance").glob("AC-*.md")):
        text = path.read_text(encoding="utf-8")
        heading = _HEADING_RE.search(text)
        criterion_id = heading.group(1) if heading else path.stem
        covers = _COVERS_RE.search(text)
        kind = _KIND_RE.search(text, covers.end() if covers else 0)
        found.append(
            _Criterion(
                id=criterion_id,
                covers=covers.group(1) if covers else None,
                kind=kind.group(1) if kind else "compiled",
                freeform=_GHERKIN_RE.search(text) is None,
            )
        )
    return found


# ---------------------------------------------------------------- drift


def _param_names(text):
    parts = []
    depth = 0
    current = ""
    for ch in text:
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append(current)
            current = ""
        else:
            current += ch
    parts.append(current)
    names = []
    for part in parts:
        match = re.match(r"\s*\*{0,2}([A-Za-z_]\w*)", part)
        if match:
            names.append(match.group(1))
    return names


def _documented(text):
    match = _BLOCK_RE.search(text)
    block = match.group(1) if match else ""
    found = []
    for m in re.finditer(r"(?m)^([A-Za-z_]\w*)\(", block):
        depth = 0
        i = m.end() - 1
        while i < len(block):
            ch = block[i]
            if ch in "([{":
                depth += 1
            elif ch in ")]}":
                depth -= 1
                if depth == 0:
                    break
            i += 1
        if re.match(r"\s*(->|:)", block[i + 1:]):
            found.append((m.group(1), _param_names(block[m.end():i])))
    return found


def _load_code(code_dir, module_name):
    flat = code_dir / f"{module_name}.py"
    package = code_dir / module_name / "__init__.py"
    if flat.is_file():
        path = flat
    elif package.is_file():
        path = package
    else:
        return None
    try:
        return _load_path(path, module_name)
    except Exception:
        return None


def _drift(spec_dir, code_dir, module_name):
    interface = spec_dir / "interface"
    documented = []
    for name in ("library.md", "cli.md"):
        doc = interface / name
        if doc.is_file():
            documented += _documented(doc.read_text(encoding="utf-8"))
    module = _load_code(code_dir, module_name)
    if module is None:
        return True
    for name, params in documented:
        obj = getattr(module, name, None)
        if not callable(obj):
            return True
        try:
            actual = list(inspect.signature(obj).parameters)
        except (TypeError, ValueError):
            return True
        if actual != params:
            return True
    if (interface / "cli.md").is_file() and not callable(getattr(module, "main", None)):
        return True
    return False


# ---------------------------------------------------------------- running


def _kill_tree(proc):
    listing = subprocess.run(
        ["ps", "-eo", "pid=,ppid="], capture_output=True, text=True
    ).stdout
    children = {}
    for line in listing.split("\n"):
        parts = line.split()
        if len(parts) == 2:
            children.setdefault(int(parts[1]), []).append(int(parts[0]))
    stack = [proc.pid]
    found = []
    while stack:
        for child in children.get(stack.pop(), []):
            found.append(child)
            stack.append(child)
    for pid in found:
        try:
            os.kill(pid, signal.SIGKILL)
        except OSError:
            pass
    proc.kill()
    proc.wait()


def _run(cmd, cwd, env, timeout):
    start = time.monotonic()
    proc = subprocess.Popen(
        cmd,
        cwd=str(cwd),
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    try:
        code = proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        _kill_tree(proc)
        return None, time.monotonic() - start
    return code, time.monotonic() - start


def _env(code_dir, plug, assets_json, interpreter, record=None):
    env = dict(os.environ)
    env["PYTHONPATH"] = str(code_dir) + os.pathsep + str(plug)
    env["HOTDOCS_ASSETS"] = assets_json
    env["HOTDOCS_PYTHON"] = str(interpreter)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.pop("HOTDOCS_FAILURE_RECORD", None)
    if record is not None:
        env["HOTDOCS_FAILURE_RECORD"] = str(record)
    return env


def _detail_from_record(record, code):
    lines = record.read_text(encoding="utf-8").splitlines() if record.is_file() else []
    if not lines:
        return {"message": f"pytest exited {code}", "expected": None, "actual": None}
    entry = json.loads(lines[0])
    op = entry["op"]
    left = _literal(entry["left"])
    right = _literal(entry["right"])
    if op in ("in", "not in"):
        expected, actual = left, right
    else:
        expected, actual = right, left
    return {
        "message": f"assert {entry['left']} {op} {entry['right']} failed",
        "expected": expected,
        "actual": actual,
    }


def _fail(entry, origin, message, expected=None, actual=None):
    entry["result"] = "fail"
    entry["failure_origin"] = origin
    entry["failure_detail"] = {"message": message, "expected": expected, "actual": actual}


def _javascript(copy):
    files = sorted(
        (p for p in copy.rglob("*.py") if "__pycache__" not in p.relative_to(copy).parts),
        key=lambda p: p.relative_to(copy).as_posix(),
    )
    for path in files:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        docstrings = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and node.body:
                first = node.body[0]
                if (
                    isinstance(first, ast.Expr)
                    and isinstance(first.value, ast.Constant)
                    and isinstance(first.value.value, str)
                ):
                    docstrings.add(id(first.value))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Constant)
                and isinstance(node.value, str)
                and id(node) not in docstrings
                and len(node.value) >= 200
                and _JS_RE.search(node.value)
                and (";" in node.value or "{" in node.value)
            ):
                rel = path.relative_to(copy).as_posix()
                return (
                    f"javascript in a string at {rel}:{node.lineno}; "
                    "declare it as an asset (specs/architecture/asset-kinds.md)"
                )
    return None


def _baseline_error(code):
    if code is None:
        return "mutation baseline timed out in the sandbox after 300 seconds"
    return f"mutation baseline failed in the sandbox: pytest exited {code}"


# ---------------------------------------------------------------- context


class _Context:
    def __init__(self, component_id, repo_root, work, judge, test_author):
        self.component_id = component_id
        self.repo_root = repo_root
        self.root = repo_root.absolute()
        self.slug = _slug(component_id)
        self.module_name = self.slug.replace("-", "_")
        self.spec_dir = self.root / "specs" / "components" / self.slug
        self.work = work
        self.judge = judge
        self.test_author = test_author
        self.plug = work / "plug"
        self.plug.mkdir()
        (self.plug / "hotdocs_asset_runner.py").write_text(_PLUGIN_SOURCE, encoding="utf-8")
        self.authored_dir = work / "authored"
        self.authored_dir.mkdir()
        self.modules = {}
        self.bundles = {}
        self.records = 0
        self.interpreter = sys.executable
        self.assets = []
        self.adapters = {}
        self.mutation_tests = []

    def dependency(self, rel_dir, module):
        key = (str(self.root), module)
        if key not in self.modules:
            base = self.root / rel_dir
            if not base.is_dir():
                base = _tool_root() / rel_dir
            path = base / f"{module}.py"
            if not path.is_file():
                path = base / module / "__init__.py"
            self.modules[key] = _load_path(path, module)
        return self.modules[key]

    def bundle(self, crit):
        if crit.id not in self.bundles:
            assembler = self.dependency("gen/spec-bundle-assembler", "spec_bundle_assembler")
            self.bundles[crit.id] = assembler.assemble_criterion(
                self.component_id, crit.id, self.repo_root
            )
        return self.bundles[crit.id]

    def assets_json(self, code_dir):
        return json.dumps(
            [
                {
                    "path": path,
                    "file": str(code_dir / path),
                    "adapter": str(self.adapters[kind][0]),
                }
                for kind, path in self.assets
            ]
        )

    def criterion_run(self, targets, code_dir):
        self.records += 1
        record = self.work / f"record_{self.records}.jsonl"
        cmd = [str(self.interpreter), "-m", "pytest", *[str(t) for t in targets], "-p", "hotdocs_asset_runner"]
        env = _env(code_dir, self.plug, self.assets_json(code_dir), self.interpreter, record)
        code, _ = _run(cmd, self.root, env, DEFAULT_TEST_TIMEOUT)
        if code == 0:
            return None
        if code is None:
            return {
                "message": f"timed out after {DEFAULT_TEST_TIMEOUT:g} seconds",
                "expected": None,
                "actual": None,
            }
        return _detail_from_record(record, code)


def _entry(crit):
    return {"id": crit.id, "covers": crit.covers, "kind": crit.kind, "result": "pass"}


def _record_run(entry, detail):
    if detail is not None:
        _fail(entry, "implementation", detail["message"], detail["expected"], detail["actual"])


def _judge(ctx, crit, entry):
    entry["rationale"] = None
    if ctx.judge is None:
        entry["result"] = "skipped"
        return
    outcome = ctx.judge(ctx.bundle(crit))
    if isinstance(outcome, Mapping) or hasattr(outcome, "result") or hasattr(outcome, "verdict"):
        value = _get(outcome, "result")
        if value is None:
            value = _get(outcome, "verdict")
        entry["rationale"] = _get(outcome, "rationale")
    else:
        value = outcome
    entry["result"] = "pass" if value is True or value == "pass" else "fail"


# ---------------------------------------------------------------- generated-test


def _author(ctx, crit, bundle, entry):
    result = ctx.test_author(bundle)
    error = _get(result, "model_call_error")
    if error and _get(error, "category") in _RETRY_CATEGORIES:
        result = ctx.test_author(bundle)
        error = _get(result, "model_call_error")
    entry["test_authoring"] = {
        "model": _get(result, "model"),
        "seed": _get(result, "seed"),
        "prompt_version": _get(result, "prompt_version"),
        "cache_hit": _get(result, "cache_hit"),
    }
    if error:
        return None, f"test authoring failed: {_get(error, 'category')}: {_get(error, 'message')}"
    content = _get(_get(result, "file"), "content")
    path = ctx.authored_dir / _test_filename(crit.id)
    path.write_text(content, encoding="utf-8")
    return path, None


def _probe(ctx, path, bundle):
    probe = ctx.dependency("gen/test-probe", "test_probe").probe
    kwargs = {}
    if "interpreter" in inspect.signature(probe).parameters:
        kwargs["interpreter"] = ctx.interpreter
    report = probe(path.read_text(encoding="utf-8"), bundle, ctx.module_name, **kwargs)
    if _get(report, "ok"):
        return None
    kinds = []
    for finding in _get(report, "findings") or []:
        kind = _get(finding, "kind")
        if _get(finding, "severity") == "error" and kind not in kinds:
            kinds.append(kind)
    return "test failed its probe: " + ", ".join(str(k) for k in kinds)


def _generated(ctx, crit, entry, code_dir):
    bundle = ctx.bundle(crit)
    cache = ctx.root / "verification" / ctx.slug / "generated-test" / _test_filename(crit.id)
    path = None
    authored = False
    if cache.is_file():
        text = cache.read_text(encoding="utf-8")
        if (text.splitlines() or [""])[0] == _header(bundle):
            path = cache
    if path is None:
        if ctx.test_author is None:
            _fail(entry, "test", "no cached test and no test_author configured")
            return
        path, error = _author(ctx, crit, bundle, entry)
        if error:
            _fail(entry, "test", error)
            return
        authored = True
    problem = _probe(ctx, path, bundle)
    if problem and not authored and ctx.test_author is not None:
        path, error = _author(ctx, crit, bundle, entry)
        if error:
            _fail(entry, "test", error)
            return
        authored = True
        problem = _probe(ctx, path, bundle)
    if problem:
        _fail(entry, "test", problem)
        return
    _record_run(entry, ctx.criterion_run([path], code_dir))
    if entry["result"] == "pass":
        ctx.mutation_tests.append((entry, path, not authored))


# ---------------------------------------------------------------- mutation


def _mutation(ctx):
    tests = list(ctx.mutation_tests)
    if not tests:
        return None, None
    sandbox = ctx.work / "sandbox"
    gen = sandbox / "gen"
    copy = gen / ctx.slug
    shutil.copytree(ctx.root / "gen" / ctx.slug, copy, ignore=shutil.ignore_patterns("__pycache__"))
    for directory in sorted((ctx.root / "gen").iterdir()):
        if directory.is_dir() and directory.name != ctx.slug:
            (gen / directory.name).symlink_to(directory)
    snapshot = {p: p.read_bytes() for p in copy.rglob("*") if p.is_file()}
    js = _javascript(copy)
    if js:
        return None, js
    env = _env(copy, ctx.plug, ctx.assets_json(copy), ctx.interpreter)

    def run(paths, timeout):
        cmd = [
            str(ctx.interpreter), "-m", "pytest", "--noconftest",
            "-p", "hotdocs_asset_runner", *[str(p) for p in paths],
        ]
        return _run(cmd, copy, env, timeout)

    def restore():
        for p, data in snapshot.items():
            p.write_bytes(data)

    code, elapsed = run([t[1] for t in tests], DEFAULT_TEST_TIMEOUT)
    if code != 0:
        faulty = [t for t in tests if run([t[1]], DEFAULT_TEST_TIMEOUT)[0] != 0]
        if not faulty:
            return None, _baseline_error(code)
        for entry, path, from_cache in faulty:
            _fail(entry, "test", "test fails in the mutation sandbox")
            if from_cache:
                path.unlink()
        tests = [t for t in tests if t not in faulty]
        if not tests:
            return None, None
        code, elapsed = run([t[1] for t in tests], DEFAULT_TEST_TIMEOUT)
        if code != 0:
            return None, _baseline_error(code)
    timeout = max(2.0, 10 * elapsed)
    paths = [t[1] for t in tests]
    killed = 0
    total = 0
    targets = [("python", ctx.adapters["python"][1], copy)] + [
        (kind, ctx.adapters[kind][1], copy / path) for kind, path in ctx.assets
    ]
    for kind, adapter, target in targets:
        try:
            sites = adapter.strength_sites(target)
        except Exception as exc:
            return None, f"{kind} adapter failed: {type(exc).__name__}: {exc}"
        for site in sites:
            try:
                adapter.apply_site(target, site)
            except Exception as exc:
                restore()
                return None, f"{kind} adapter failed: {type(exc).__name__}: {exc}"
            code, _ = run(paths, timeout)
            total += 1
            if code != 0:
                killed += 1
            restore()
    return (killed / total if total else 1.0), None


# ---------------------------------------------------------------- verify


def _provision(ctx, declared):
    kinds = list(dict.fromkeys(["python"] + [kind for kind, _ in declared]))
    reports = {}
    for kind in kinds:
        module = kind.replace("-", "_")
        rel = Path("gen") / f"kind-{kind}" / f"kind_{module}.py"
        path = ctx.root / rel
        if not path.is_file():
            path = _tool_root() / rel
        if not path.is_file():
            ctx.adapters[kind] = None
            continue
        adapter = _load_path(path, f"kind_{module}")
        ctx.adapters[kind] = (path.absolute(), adapter)
        reports[kind] = adapter.provision(ctx.repo_root)
    failure = None
    for kind in kinds:
        if ctx.adapters[kind] is None:
            failure = f"unknown asset kind: {kind}"
            break
        if not _get(reports[kind], "ok"):
            failure = _get(reports[kind], "reason")
            break
    entries = []
    for kind, path in [("python", ".")] + list(declared):
        definition = ctx.root / "specs" / "architecture" / f"asset-kind-{kind}.md"
        adapter = ctx.adapters[kind]
        report = reports.get(kind)
        entries.append(
            {
                "kind": kind,
                "path": path,
                "definition_sha256": _sha256_file(definition) if definition.is_file() else None,
                "adapter_sha256": _sha256_file(adapter[0]) if adapter else None,
                "versions": _get(report, "versions", {}) if adapter else {},
                "lockfile_sha256": _get(report, "lockfile_sha256") if adapter else None,
            }
        )
    ctx.interpreter = _get(reports.get("python"), "interpreter")
    return entries, failure


def _requirement_results(requirement_ids, entries):
    return {
        rid: "pass" if all(e["result"] == "pass" for e in entries if e["covers"] == rid) else "fail"
        for rid in requirement_ids
    }


def _verify_unsealed(ctx, criteria, declared):
    ctx.assets = list(declared)
    code_dir = ctx.root / "gen" / ctx.slug
    assets, failure = _provision(ctx, declared)
    drift = _drift(ctx.spec_dir, code_dir, ctx.module_name)
    entries = []
    compiled = None
    for crit in criteria:
        entry = _entry(crit)
        entries.append(entry)
        if crit.kind == "llm-judge":
            _judge(ctx, crit, entry)
        elif failure is not None:
            _fail(entry, "environment", failure)
        elif crit.kind == "compiled":
            if compiled is None:
                compiler = ctx.dependency("pipeline/criterion-compiler", "criterion_compiler")
                report = compiler.compile(ctx.component_id, ctx.repo_root, out_dir=ctx.work / "compiled")
                compiled = {_get(o, "criterion_id"): o for o in _get(report, "outputs") or []}
            output = compiled.get(crit.id)
            if _get(output, "status") != "compiled":
                _fail(entry, "implementation", _get(output, "message", "criterion was not compiled"))
                continue
            file = Path(_get(output, "file"))
            if not file.is_absolute():
                file = ctx.root / file
            _record_run(entry, ctx.criterion_run([file], code_dir))
        else:
            _generated(ctx, crit, entry, code_dir)
    score, error = _mutation(ctx)
    generated = [c for c in criteria if c.kind == "generated-test"]
    bar = 0.9 if any(c.freeform for c in generated) else 0.8
    failed = (
        any(e["result"] == "fail" for e in entries)
        or drift
        or error is not None
        or (score is not None and score < bar)
    )
    return entries, drift, score, error, assets, failed


def _characterization_tests(ctx):
    found = []
    for path in sorted((ctx.root / "verification" / ctx.slug).glob("test_*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                found.append((node.name, f"{path}::{node.name}"))
            elif isinstance(node, ast.ClassDef):
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        found.append((item.name, f"{path}::{node.name}::{item.name}"))
    return found


def _verify_sealed(ctx, criteria, source_path):
    code_dir = ctx.root / source_path
    missing = not code_dir.is_dir()
    drift = True if missing else _drift(ctx.spec_dir, code_dir, ctx.module_name)
    tests = _characterization_tests(ctx)
    entries = []
    for crit in criteria:
        entry = _entry(crit)
        entries.append(entry)
        if crit.kind == "llm-judge":
            _judge(ctx, crit, entry)
            continue
        prefix = "test_" + crit.id.lower().replace("-", "_")
        matching = [nodeid for name, nodeid in tests if name == prefix or name.startswith(prefix + "_")]
        if not matching:
            _fail(entry, "implementation", "no characterization test")
            continue
        _record_run(entry, ctx.criterion_run(matching, code_dir))
    failed = missing or drift or any(e["result"] == "fail" for e in entries)
    return entries, drift, None, None, [], failed


def verify(component_id, repo_root, judge=None, test_author=None):
    repo_root = Path(repo_root)
    criteria = None
    with tempfile.TemporaryDirectory() as work:
        ctx = _Context(component_id, repo_root, Path(work), judge, test_author)
        sealed, source_path, declared = _component_meta(
            (ctx.spec_dir / "component.md").read_text(encoding="utf-8")
        )
        criteria = _criteria(ctx.spec_dir)
        requirement_ids = sorted(p.stem for p in (ctx.spec_dir / "requirements").glob("R-*.md"))
        if sealed:
            result = _verify_sealed(ctx, criteria, source_path)
        else:
            result = _verify_unsealed(ctx, criteria, declared)
    entries, drift, score, error, assets, failed = result
    return VerificationReport(
        component_id=component_id,
        criteria=entries,
        requirement_results=_requirement_results(requirement_ids, entries),
        interface_drift=drift,
        mutation_score=score,
        mutation_error=error,
        assets=assets,
        overall="fail" if failed else "pass",
    )


# ---------------------------------------------------------------- CLI


def _usage(cause):
    print(f"usage error: {cause}", file=sys.stderr)
    print(USAGE, file=sys.stderr)
    return 2


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    component_id = None
    repo_root = "."
    fmt = "text"
    i = 0
    while i < len(args):
        token = args[i]
        flag = None
        value = None
        for name in ("--repo-root", "--format"):
            if token == name:
                if i + 1 >= len(args):
                    return _usage(f"{name} needs a value")
                i += 1
                value = args[i]
                flag = name
            elif token.startswith(name + "="):
                value = token[len(name) + 1:]
                flag = name
        if flag == "--repo-root":
            repo_root = value
        elif flag == "--format":
            fmt = value
        elif token.startswith("-") or component_id is not None:
            return _usage(f"unknown argument: {token}")
        else:
            component_id = token
        i += 1
    if component_id is None:
        return _usage("missing <component-id>")
    if fmt not in ("json", "text"):
        return _usage(f"invalid --format: {fmt}")
    root = Path(repo_root)
    if not (root / "specs" / "components" / _slug(component_id) / "component.md").is_file():
        return _usage(f"unknown component: {component_id}")
    report = verify(component_id, root)
    if fmt == "json":
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print(f"{report.component_id}: {report.overall}")
        for entry in report.criteria:
            print(f"  {entry['id']}: {entry['result']}")
    return 0 if report.overall == "pass" else 1
