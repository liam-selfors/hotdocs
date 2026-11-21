"""Test Probe: checks a generated test file for defects of its own."""

import ast
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from collections.abc import Mapping
from dataclasses import dataclass, field

import pyflakes.api
import pyflakes.messages

GATE_VERSION = "test-probe@1.3.0"

_TEST_FILE = "test_probe_target.py"
_ASSET_PLUGIN = "hotdocs_probe_assets"

_STUB_SOURCE = '''class HotdocsProbeStubReached(BaseException):
    pass


class _Stub:
    def __init__(self, name):
        self._name = name

    def __call__(self, *args, **kwargs):
        raise HotdocsProbeStubReached(self._name)

    def __getattr__(self, name):
        return _Stub(self._name + "." + name)


def __getattr__(name):
    if name.startswith("__"):
        raise AttributeError(name)
    return _Stub(name)
'''

_ASSET_SOURCE = '''import pytest


class HotdocsProbeStubReached(BaseException):
    pass


def _reached(*args, **kwargs):
    raise HotdocsProbeStubReached("asset_runner")


@pytest.fixture
def asset_runner():
    def runner(path):
        return _reached

    return runner
'''

_RESOLVE_SCRIPT = (
    "import importlib.util, json, sys\n"
    "print(json.dumps([p for p in sys.argv[1:] "
    "if importlib.util.find_spec(p) is None]))\n"
)

_CHECK_ORDER = {
    "syntax_error": 0,
    "undefined_name": 1,
    "unknown_import": 2,
    "fake_signature_mismatch": 3,
    "collection_error": 4,
    "test_bug": 4,
    "probe_timeout": 4,
    "vacuous": 4,
}

_IMPORT_GUARDS = ("ImportError", "ModuleNotFoundError")
_BUG_PREFIXES = ("NameError", "UnboundLocalError", "ImportError", "ModuleNotFoundError")
_REACHED = "HotdocsProbeStubReached"


@dataclass
class ProbeReport:
    ok: bool
    findings: list = field(default_factory=list)
    tests_run: int = 0
    tests_reached: int = 0

    def to_dict(self):
        return {
            "ok": self.ok,
            "findings": [dict(f) for f in self.findings],
            "tests_run": self.tests_run,
            "tests_reached": self.tests_reached,
        }


def _finding(kind, line, message):
    severity = "warn" if kind == "vacuous" else "error"
    return {"kind": kind, "severity": severity, "line": line, "message": message}


def _report(findings, tests_run, tests_reached):
    ordered = sorted(
        findings,
        key=lambda f: (_CHECK_ORDER[f["kind"]], f["line"] or 0, f["message"]),
    )
    ok = not any(f["severity"] == "error" for f in ordered)
    return ProbeReport(ok=ok, findings=ordered, tests_run=tests_run, tests_reached=tests_reached)


# --- R-PROBE-002 -----------------------------------------------------------

class _Reporter:
    def __init__(self):
        self.messages = []

    def flake(self, message):
        self.messages.append(message)


def _undefined_names(test_source):
    reporter = _Reporter()
    pyflakes.api.check(test_source, _TEST_FILE, reporter)
    findings = []
    for m in reporter.messages:
        if isinstance(m, pyflakes.messages.UndefinedName):
            findings.append(
                _finding("undefined_name", m.lineno, "undefined name '%s'" % m.message_args[0])
            )
    return findings


# --- R-PROBE-003 -----------------------------------------------------------

def _guards_import(handlers):
    for handler in handlers:
        t = handler.type
        elts = t.elts if isinstance(t, ast.Tuple) else [t]
        for e in elts:
            if isinstance(e, ast.Name) and e.id in _IMPORT_GUARDS:
                return True
    return False


def _collect_imports(node, guarded, out):
    if isinstance(node, ast.Import):
        if not guarded:
            for alias in node.names:
                out.add((node.lineno, alias.name.split(".")[0]))
        return
    if isinstance(node, ast.ImportFrom):
        if not guarded and node.level == 0:
            out.add((node.lineno, node.module.split(".")[0]))
        return
    if isinstance(node, ast.Try) and _guards_import(node.handlers):
        for stmt in node.body:
            _collect_imports(stmt, True, out)
        for other in node.handlers + node.orelse + node.finalbody:
            _collect_imports(other, guarded, out)
        return
    for child in ast.iter_child_nodes(node):
        _collect_imports(child, guarded, out)


def _unresolved(parts, interpreter):
    if interpreter is None:
        return {p for p in parts if importlib.util.find_spec(p) is None}
    proc = subprocess.run(
        [interpreter, "-c", _RESOLVE_SCRIPT, *parts],
        capture_output=True,
        text=True,
    )
    return set(json.loads(proc.stdout))


def _unknown_imports(tree, names, interpreter):
    imports = set()
    _collect_imports(tree, False, imports)
    remaining = sorted(
        {part for _, part in imports if part not in names and part not in sys.stdlib_module_names}
    )
    if not remaining:
        return []
    missing = _unresolved(remaining, interpreter)
    return [
        _finding("unknown_import", line, "cannot import '%s'" % part)
        for line, part in imports
        if part in missing
    ]


# --- R-PROBE-004 -----------------------------------------------------------

def _split_params(params):
    parts = []
    depth = 0
    cur = ""
    for ch in params:
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append(cur)
            cur = ""
        else:
            cur += ch
    parts.append(cur)
    return [p.strip() for p in parts if p.strip() not in ("", "*", "/", "self")]


def _signatures(dependency_interfaces):
    sigs = {}
    for component_id, text in dependency_interfaces.items():
        for m in re.finditer(r"([A-Za-z_]\w*)\(", text):
            start = m.end()
            depth = 1
            end = None
            for i in range(start, len(text)):
                if text[i] == "(":
                    depth += 1
                elif text[i] == ")":
                    depth -= 1
                    if depth == 0:
                        end = i
                        break
            if end is None or not re.match(r"\s*->", text[end + 1:]):
                continue
            count = len(_split_params(text[start:end]))
            sigs.setdefault(m.group(1), []).append((component_id, count))
    return sigs


def _arity_finding(fn, name, line, sigs):
    a = fn.args
    if a.vararg is not None or a.kwarg is not None:
        return None
    n = len(a.posonlyargs) + len(a.args) + len(a.kwonlyargs)
    candidates = sigs[name]
    if any(count == n for _, count in candidates):
        return None
    component_id, m = candidates[0]
    return _finding(
        "fake_signature_mismatch",
        line,
        "%s takes %d parameters; the interface of %s gives %d" % (name, n, component_id, m),
    )


def _fake_mismatches(tree, dependency_interfaces):
    sigs = _signatures(dependency_interfaces)
    fn_types = (ast.FunctionDef, ast.AsyncFunctionDef)
    results = set()

    # Fakes inside string literals that parse as a fake module's source.
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            try:
                sub = ast.parse(node.value)
            except (SyntaxError, ValueError):
                continue
            for stmt in sub.body:
                if isinstance(stmt, fn_types) and stmt.name in sigs:
                    f = _arity_finding(stmt, stmt.name, node.lineno + stmt.lineno - 1, sigs)
                    if f is not None:
                        results.add((f["line"], f["message"]))

    # Top-level defs and simple aliases of them, installed under a dependency name.
    defs = {stmt.name: stmt for stmt in tree.body if isinstance(stmt, fn_types)}
    for stmt in tree.body:
        if (
            isinstance(stmt, ast.Assign)
            and len(stmt.targets) == 1
            and isinstance(stmt.targets[0], ast.Name)
            and isinstance(stmt.value, ast.Name)
            and stmt.value.id in defs
        ):
            defs[stmt.targets[0].id] = defs[stmt.value.id]

    installs = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and len(node.args) == 3:
            func = node.func
            is_setattr = (isinstance(func, ast.Name) and func.id == "setattr") or (
                isinstance(func, ast.Attribute)
                and func.attr == "setattr"
                and isinstance(func.value, ast.Name)
                and func.value.id == "monkeypatch"
            )
            name_arg, fn_arg = node.args[1], node.args[2]
            if (
                is_setattr
                and isinstance(name_arg, ast.Constant)
                and isinstance(name_arg.value, str)
                and isinstance(fn_arg, ast.Name)
            ):
                installs.append((name_arg.value, fn_arg.id))
        elif isinstance(node, ast.Assign) and isinstance(node.value, ast.Name):
            for target in node.targets:
                if isinstance(target, ast.Attribute):
                    installs.append((target.attr, node.value.id))

    for name, fn_name in installs:
        if name in sigs and fn_name in defs:
            fn = defs[fn_name]
            f = _arity_finding(fn, name, fn.lineno, sigs)
            if f is not None:
                results.add((f["line"], f["message"]))

    return [_finding("fake_signature_mismatch", line, msg) for line, msg in results]


# --- R-PROBE-005 / R-PROBE-007 ---------------------------------------------

def _stub_run(test_source, names, timeout, interpreter):
    tmp = tempfile.mkdtemp()
    try:
        with open(os.path.join(tmp, _TEST_FILE), "w") as fh:
            fh.write(test_source)
        for name in names:
            with open(os.path.join(tmp, name + ".py"), "w") as fh:
                fh.write(_STUB_SOURCE)
        with open(os.path.join(tmp, _ASSET_PLUGIN + ".py"), "w") as fh:
            fh.write(_ASSET_SOURCE)
        report_path = os.path.join(tmp, "report.xml")
        env = dict(os.environ, PYTHONPATH=tmp)
        try:
            proc = subprocess.run(
                [
                    interpreter, "-m", "pytest", "-q", "-p", "no:cacheprovider",
                    "--noconftest", "-p", _ASSET_PLUGIN,
                    "--junitxml=" + report_path, _TEST_FILE,
                ],
                cwd=tmp,
                env=env,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            return [_finding("probe_timeout", None, "stub run exceeded %s seconds" % timeout)], 0, 0

        lines = [l.strip() for l in (proc.stdout + "\n" + proc.stderr).splitlines() if l.strip()]
        last_line = lines[-1] if lines else ""
        collection_error = [_finding("collection_error", None, last_line)]

        if proc.returncode in (2, 3, 4):
            return collection_error, 0, 0

        root = ET.parse(report_path).getroot()
        testcases = []
        collect_failed = False
        for tc in root.iter("testcase"):
            error = tc.find("error")
            if error is not None and error.get("message", "") == "collection failure":
                collect_failed = True
            else:
                testcases.append(tc)
        if collect_failed or not testcases:
            return collection_error, 0, 0

        findings = []
        reached = 0
        for tc in testcases:
            name = tc.get("name", "")
            failure = tc.find("failure")
            error = tc.find("error")
            skipped = tc.find("skipped")
            fmsg = failure.get("message", "") if failure is not None else ""
            if failure is not None and _REACHED in fmsg:
                reached += 1
            elif failure is not None and fmsg.startswith(_BUG_PREFIXES):
                findings.append(_finding("test_bug", None, "%s: %s" % (name, fmsg)))
            elif error is not None:
                findings.append(
                    _finding("test_bug", None, "%s: %s" % (name, error.get("message", "")))
                )
            elif failure is None and skipped is None:
                findings.append(
                    _finding(
                        "vacuous",
                        None,
                        "%s passed without reaching the code under test" % name,
                    )
                )
        return findings, len(testcases), reached
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# --- probe -----------------------------------------------------------------

def _dependency_interfaces(criterion_bundle):
    if isinstance(criterion_bundle, Mapping):
        value = criterion_bundle.get("dependency_interfaces", {})
    else:
        value = getattr(criterion_bundle, "dependency_interfaces", {})
    return value


def probe(test_source, criterion_bundle, module_name, *, timeout=60.0, interpreter=None):
    names = [module_name] if isinstance(module_name, str) else list(module_name)

    try:
        tree = ast.parse(test_source)
    except SyntaxError as e:
        return _report([_finding("syntax_error", e.lineno, e.msg)], 0, 0)

    findings = []
    findings.extend(_undefined_names(test_source))
    findings.extend(_unknown_imports(tree, names, interpreter))
    findings.extend(_fake_mismatches(tree, _dependency_interfaces(criterion_bundle)))

    if any(f["severity"] == "error" for f in findings):
        return _report(findings, 0, 0)

    run_findings, tests_run, tests_reached = _stub_run(
        test_source, names, timeout, interpreter or sys.executable
    )
    findings.extend(run_findings)
    return _report(findings, tests_run, tests_reached)
