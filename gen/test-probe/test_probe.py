"""Static and stub-run checks of one generated test's source."""

import ast
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import importlib.util
import xml.etree.ElementTree as ET
from collections.abc import Mapping
from dataclasses import dataclass, field

import pyflakes.api
import pyflakes.messages

GATE_VERSION = "test-probe@1.4.0"

_TARGET = "test_probe_target.py"

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

_ASSET_PLUGIN_SOURCE = '''import json
import os

import pytest


class HotdocsProbeStubReached(BaseException):
    pass


class HotdocsProbeUndeclaredAsset(KeyError):
    pass


def _reached(*args, **kwargs):
    raise HotdocsProbeStubReached("asset_runner")


def _declared(path):
    listed = os.environ.get("HOTDOCS_PROBE_ASSETS")
    if listed is not None:
        return path in json.loads(listed)
    parts = path.replace("\\\\", "/").split("/")
    return not (path.startswith("/") or parts[0] == "gen" or ".." in parts)


@pytest.fixture
def asset_runner():
    def runner(path):
        if not _declared(path):
            raise HotdocsProbeUndeclaredAsset(
                f"asset_runner: {path!r} is not a declared asset path")
        return _reached

    return runner
'''

_FIND_SPEC_SCRIPT = (
    "import importlib.util, json, sys\n"
    "print(json.dumps([p for p in sys.argv[1:] "
    "if importlib.util.find_spec(p) is None]))\n"
)

_SIG_START = re.compile(r"([A-Za-z_]\w*)\s*\(")
_ARROW = re.compile(r"\s*->")

_BUG_PREFIXES = ("NameError", "UnboundLocalError", "ImportError",
                 "ModuleNotFoundError")
_SETUP_ASSERTION = 'failed on setup with "AssertionError"'


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


def _finding(kind, line, message, severity="error"):
    return {"kind": kind, "severity": severity, "line": line,
            "message": message}


def _ordered(findings):
    unique = {(f["line"], f["message"], f["kind"]): f for f in findings}
    return sorted(unique.values(),
                  key=lambda f: (f["line"] is None, f["line"] or 0,
                                 f["message"]))


def _report(findings, tests_run=0, tests_reached=0):
    return ProbeReport(
        ok=not any(f["severity"] == "error" for f in findings),
        findings=findings,
        tests_run=tests_run,
        tests_reached=tests_reached,
    )


# R-PROBE-002 --------------------------------------------------------------

class _Collector:
    def __init__(self):
        self.messages = []

    def unexpectedError(self, filename, msg):
        pass

    def syntaxError(self, filename, msg, lineno, offset, text):
        pass

    def flake(self, message):
        self.messages.append(message)


def _check_pyflakes(test_source):
    collector = _Collector()
    pyflakes.api.check(test_source, _TARGET, collector)
    return [
        _finding("undefined_name", m.lineno,
                 f"undefined name '{m.message_args[0]}'")
        for m in collector.messages
        if isinstance(m, pyflakes.messages.UndefinedName)
    ]


# R-PROBE-003 --------------------------------------------------------------

def _guards_import_error(handler):
    names = handler.type.elts if isinstance(handler.type, ast.Tuple) \
        else [handler.type]
    for node in names:
        name = node.id if isinstance(node, ast.Name) else \
            getattr(node, "attr", None)
        if name in ("ImportError", "ModuleNotFoundError"):
            return True
    return False


def _guarded_imports(tree):
    guarded = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Try) and any(
                _guards_import_error(h) for h in node.handlers):
            for stmt in node.body:
                guarded.update(id(n) for n in ast.walk(stmt))
    return guarded


def _check_imports(tree, names, interpreter):
    guarded = _guarded_imports(tree)
    pending = []
    for node in ast.walk(tree):
        if id(node) in guarded:
            continue
        if isinstance(node, ast.Import):
            parts = [alias.name.split(".")[0] for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.level == 0:
            parts = [node.module.split(".")[0]]
        else:
            continue
        for part in parts:
            if part not in names and part not in sys.stdlib_module_names:
                pending.append((node.lineno, part))
    if not pending:
        return []
    distinct = sorted({part for _, part in pending})
    if interpreter is None:
        missing = {p for p in distinct
                   if importlib.util.find_spec(p) is None}
    else:
        proc = subprocess.run(
            [interpreter, "-c", _FIND_SPEC_SCRIPT, *distinct],
            capture_output=True, text=True, env=dict(os.environ))
        missing = set(json.loads(proc.stdout))
    return [_finding("unknown_import", line, f"cannot import '{part}'")
            for line, part in pending if part in missing]


# R-PROBE-004 --------------------------------------------------------------

def _param_count(text, start):
    depth = 0
    pieces = []
    current = []
    for i in range(start, len(text)):
        ch = text[i]
        if depth == 0 and ch == ")":
            if not _ARROW.match(text, i + 1):
                return None
            pieces.append("".join(current))
            break
        if depth == 0 and ch == ",":
            pieces.append("".join(current))
            current = []
            continue
        depth += (ch in "([{") - (ch in ")]}")
        current.append(ch)
    else:
        return None
    count = 0
    for piece in pieces:
        piece = piece.strip()
        name = piece.split(":")[0].split("=")[0].strip()
        if name and name not in ("*", "/", "self"):
            count += 1
    return count


def _signatures(interfaces):
    sigs = {}
    for component_id, text in interfaces.items():
        for match in _SIG_START.finditer(text):
            count = _param_count(text, match.end())
            if count is not None:
                sigs.setdefault(match.group(1), []).append(
                    (component_id, count))
    return sigs


def _fakes(tree):
    fakes = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            try:
                inner = ast.parse(node.value)
            except SyntaxError:
                continue
            for d in inner.body:
                if isinstance(d, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    fakes.append((d.name, d, node.lineno + d.lineno - 1))

    installable = {n.name: n for n in tree.body
                   if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    for n in tree.body:
        if (isinstance(n, ast.Assign) and len(n.targets) == 1
                and isinstance(n.targets[0], ast.Name)
                and isinstance(n.value, ast.Name)
                and n.value.id in installable):
            installable[n.targets[0].id] = installable[n.value.id]

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            is_setattr = (isinstance(func, ast.Attribute)
                          and func.attr == "setattr") or (
                isinstance(func, ast.Name) and func.id == "setattr")
            if (is_setattr and len(node.args) >= 3
                    and isinstance(node.args[1], ast.Constant)
                    and isinstance(node.args[1].value, str)
                    and isinstance(node.args[2], ast.Name)
                    and node.args[2].id in installable):
                d = installable[node.args[2].id]
                fakes.append((node.args[1].value, d, d.lineno))
        elif isinstance(node, ast.Assign) and isinstance(node.value,
                                                         ast.Name):
            if node.value.id in installable:
                d = installable[node.value.id]
                for target in node.targets:
                    if isinstance(target, ast.Attribute):
                        fakes.append((target.attr, d, d.lineno))
    return fakes


def _check_fakes(tree, interfaces):
    sigs = _signatures(interfaces)
    findings = []
    for name, d, line in _fakes(tree):
        if name not in sigs or d.args.vararg or d.args.kwarg:
            continue
        n = len(d.args.posonlyargs) + len(d.args.args) + len(
            d.args.kwonlyargs)
        options = sigs[name]
        if any(m == n for _, m in options):
            continue
        component_id, m = options[0]
        findings.append(_finding(
            "fake_signature_mismatch", line,
            f"{name} takes {n} parameters; the interface of "
            f"{component_id} gives {m}"))
    return findings


# R-PROBE-005 / R-PROBE-007 -----------------------------------------------

def _stub_run(test_source, names, timeout, interpreter, assets):
    tmp = tempfile.mkdtemp()
    try:
        with open(os.path.join(tmp, _TARGET), "w", encoding="utf-8") as fh:
            fh.write(test_source)
        for name in names:
            with open(os.path.join(tmp, name + ".py"), "w",
                      encoding="utf-8") as fh:
                fh.write(_STUB_SOURCE)
        with open(os.path.join(tmp, "hotdocs_probe_assets.py"), "w",
                  encoding="utf-8") as fh:
            fh.write(_ASSET_PLUGIN_SOURCE)
        env = dict(os.environ)
        env["PYTHONPATH"] = tmp
        env.pop("HOTDOCS_PROBE_ASSETS", None)
        if assets is not None:
            env["HOTDOCS_PROBE_ASSETS"] = json.dumps(assets)
        report_path = os.path.join(tmp, "report.xml")
        command = [interpreter, "-m", "pytest", "-q", "-p", "no:cacheprovider",
                   "--noconftest", "-p", "hotdocs_probe_assets",
                   f"--junitxml={report_path}", _TARGET]
        try:
            proc = subprocess.run(command, cwd=tmp, env=env,
                                  capture_output=True, text=True,
                                  timeout=timeout)
        except subprocess.TimeoutExpired:
            return [_finding(
                "probe_timeout", None,
                f"stub run still going after {timeout} seconds")], 0, 0
        last_line = "".join(
            (proc.stdout + proc.stderr).strip().splitlines()[-1:])
        collection = ([_finding("collection_error", None, last_line)], 0, 0)
        if proc.returncode in (2, 3, 4):
            return collection
        cases = list(ET.parse(report_path).getroot().iter("testcase"))
        if not cases or any(
                e.get("message", "") == "collection failure"
                for c in cases for e in c.findall("error")):
            return collection
        return _classify(cases)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _classify(cases):
    findings = []
    reached = 0
    setup_reached = False
    for case in cases:
        name = case.get("name", "")
        child = next((c for c in case if c.tag in ("failure", "error")),
                     None)
        if child is None:
            if case.find("skipped") is None:
                findings.append(_finding(
                    "vacuous", None,
                    f"{name} passed without reaching the code under test",
                    severity="warn"))
            continue
        message = child.get("message", "")
        if "HotdocsProbeUndeclaredAsset" in message:
            findings.append(_finding("test_bug", None, f"{name}: {message}"))
        elif "HotdocsProbeStubReached" in message:
            reached += 1
            setup_reached = setup_reached or child.tag == "error"
        elif (child.tag == "error" and message == _SETUP_ASSERTION
              and setup_reached):
            continue
        elif child.tag == "error" or message.startswith(_BUG_PREFIXES):
            findings.append(_finding("test_bug", None, f"{name}: {message}"))
    return findings, len(cases), reached


# probe --------------------------------------------------------------------

def _dependency_interfaces(criterion_bundle):
    if isinstance(criterion_bundle, Mapping):
        value = criterion_bundle.get("dependency_interfaces")
    else:
        value = getattr(criterion_bundle, "dependency_interfaces", None)
    return value or {}


def probe(test_source, criterion_bundle, module_name, *, timeout=60.0,
          interpreter=None, assets=None):
    try:
        tree = ast.parse(test_source)
    except SyntaxError as exc:
        return _report([_finding("syntax_error", exc.lineno, str(exc.msg))])

    names = [module_name] if isinstance(module_name, str) \
        else list(module_name)

    findings = []
    findings += _ordered(_check_pyflakes(test_source))
    findings += _ordered(_check_imports(tree, names, interpreter))
    findings += _ordered(_check_fakes(
        tree, _dependency_interfaces(criterion_bundle)))

    if any(f["severity"] == "error" for f in findings):
        return _report(findings)

    run_findings, tests_run, tests_reached = _stub_run(
        test_source, names, timeout, interpreter or sys.executable, assets)
    findings += _ordered(run_findings)
    return _report(findings, tests_run, tests_reached)
