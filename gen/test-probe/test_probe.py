"""Test probe: checks a generated test file for defects of its own."""

import ast
import dataclasses
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

import pyflakes.api
import pyflakes.messages

GATE_VERSION = "test-probe@1.5.0"

_TEST_FILE = "test_probe_target.py"
_PLUGIN_FILE = "hotdocs_probe_assets.py"

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

_PLUGIN_SOURCE = '''import json
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


class _DriverStub:
    def __init__(self, name):
        self._name = name

    def __getattr__(self, name):
        raise HotdocsProbeStubReached(self._name + "." + name)


def _driver_fixture(name):
    @pytest.fixture(name=name)
    def fixture():
        return _DriverStub(name)

    return fixture


for _name in json.loads(os.environ.get("HOTDOCS_PROBE_DRIVERS", "[]")):
    globals()["_driver_" + _name] = _driver_fixture(_name)
'''

_FIND_SPEC_SCRIPT = (
    "import importlib.util, json, sys\n"
    "print(json.dumps([p for p in json.loads(sys.argv[1]) "
    "if importlib.util.find_spec(p) is None]))\n"
)

_IMPORT_ERRORS = {"ImportError", "ModuleNotFoundError"}
_BUG_PREFIXES = ("NameError", "UnboundLocalError", "ImportError",
                 "ModuleNotFoundError")
_SIG_START = re.compile(r"([A-Za-z_]\w*)\s*\(")
_OPENERS = "([{"
_CLOSERS = ")]}"


@dataclasses.dataclass
class ProbeReport:
    ok: bool
    findings: list
    tests_run: int
    tests_reached: int

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


def _sorted(findings):
    return sorted(findings, key=lambda f: (f["line"] or 0, f["message"]))


def _get(obj, key, default):
    if isinstance(obj, Mapping):
        return obj.get(key, default)
    return getattr(obj, key, default)


# --- R-PROBE-002 -----------------------------------------------------------

class _Reporter:
    def __init__(self):
        self.findings = []

    def flake(self, message):
        if isinstance(message, pyflakes.messages.UndefinedName):
            self.findings.append(_finding(
                "undefined_name", message.lineno,
                f"undefined name '{message.message_args[0]}'"))

    def unexpectedError(self, filename, msg):
        pass

    def syntaxError(self, filename, msg, lineno, offset, text):
        pass


def _check_pyflakes(test_source):
    reporter = _Reporter()
    pyflakes.api.check(test_source, _TEST_FILE, reporter)
    return reporter.findings


# --- R-PROBE-003 -----------------------------------------------------------

def _catches_import_error(node):
    for handler in node.handlers:
        types = handler.type.elts if isinstance(handler.type, ast.Tuple) \
            else [handler.type]
        if any(isinstance(t, ast.Name) and t.id in _IMPORT_ERRORS
               for t in types):
            return True
    return False


def _collect_imports(tree):
    found = []

    def visit(node, guarded):
        if isinstance(node, ast.Import) and not guarded:
            for alias in node.names:
                found.append((node.lineno, alias.name.split(".")[0]))
        elif isinstance(node, ast.ImportFrom) and not guarded \
                and node.level == 0:
            found.append((node.lineno, node.module.split(".")[0]))
        if isinstance(node, ast.Try) and _catches_import_error(node):
            for child in node.body:
                visit(child, True)
            for child in node.handlers + node.orelse + node.finalbody:
                visit(child, guarded)
            return
        for child in ast.iter_child_nodes(node):
            visit(child, guarded)

    visit(tree, False)
    return found


def _missing_parts(parts, interpreter):
    if interpreter is None:
        return {p for p in parts if importlib.util.find_spec(p) is None}
    proc = subprocess.run(
        [interpreter, "-c", _FIND_SPEC_SCRIPT, json.dumps(parts)],
        capture_output=True, text=True)
    return set(json.loads(proc.stdout))


def _check_imports(tree, module_names, interpreter):
    imports = _collect_imports(tree)
    remaining = sorted({part for _, part in imports
                        if part not in module_names
                        and part not in sys.stdlib_module_names})
    missing = _missing_parts(remaining, interpreter)
    return [_finding("unknown_import", line, f"cannot import '{part}'")
            for line, part in imports if part in missing]


# --- R-PROBE-004 -----------------------------------------------------------

def _balanced(text, start):
    depth = 1
    for index in range(start, len(text)):
        char = text[index]
        if char in _OPENERS:
            depth += 1
        elif char in _CLOSERS:
            depth -= 1
            if depth == 0:
                return text[start:index], index + 1
    return None, None


def _split_params(params_text):
    parts = []
    depth = 0
    current = ""
    for char in params_text:
        if char in _OPENERS:
            depth += 1
        elif char in _CLOSERS:
            depth -= 1
        if char == "," and depth == 0:
            parts.append(current)
            current = ""
        else:
            current += char
    parts.append(current)
    count = 0
    for part in parts:
        name = part.split(":")[0].split("=")[0].strip()
        if name in ("", "*", "/", "self"):
            continue
        if not name.lstrip("*").isidentifier():
            return None
        count += 1
    return count


def _signatures(interfaces):
    sigs = {}
    for component_id, text in interfaces.items():
        for match in _SIG_START.finditer(text):
            params_text, end = _balanced(text, match.end())
            if params_text is None or not re.match(r"\s*->", text[end:]):
                continue
            count = _split_params(params_text)
            if count is None:
                continue
            sigs.setdefault(match.group(1), []).append((component_id, count))
    return sigs


def _is_def(node):
    return isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))


def _collect_fakes(tree, sigs):
    fakes = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            try:
                inner = ast.parse(node.value)
            except (SyntaxError, ValueError):
                continue
            for item in inner.body:
                if _is_def(item) and item.name in sigs:
                    fakes.append((item.name, item,
                                  node.lineno + item.lineno - 1))

    defs = {item.name: item for item in tree.body if _is_def(item)}
    resolvable = dict(defs)
    for item in tree.body:
        if isinstance(item, ast.Assign) and len(item.targets) == 1 \
                and isinstance(item.targets[0], ast.Name) \
                and isinstance(item.value, ast.Name) \
                and item.value.id in defs:
            resolvable[item.targets[0].id] = defs[item.value.id]

    installs = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and len(node.args) == 3 \
                and ((isinstance(node.func, ast.Name)
                      and node.func.id == "setattr")
                     or (isinstance(node.func, ast.Attribute)
                         and node.func.attr == "setattr")) \
                and isinstance(node.args[1], ast.Constant) \
                and isinstance(node.args[1].value, str) \
                and isinstance(node.args[2], ast.Name) \
                and node.args[2].id in resolvable:
            installs.append((node.args[1].value, resolvable[node.args[2].id]))
        elif isinstance(node, ast.Assign) \
                and isinstance(node.value, ast.Name) \
                and node.value.id in resolvable:
            for target in node.targets:
                if isinstance(target, ast.Attribute):
                    installs.append((target.attr, resolvable[node.value.id]))

    seen = set()
    for name, fn in installs:
        if name in sigs and (name, id(fn)) not in seen:
            seen.add((name, id(fn)))
            fakes.append((name, fn, fn.lineno))
    return fakes


def _check_fakes(tree, interfaces):
    sigs = _signatures(interfaces)
    findings = []
    for name, fn, line in _collect_fakes(tree, sigs):
        args = fn.args
        if args.vararg or args.kwarg:
            continue
        count = len(args.posonlyargs) + len(args.args) + len(args.kwonlyargs)
        entries = sigs[name]
        if count not in [m for _, m in entries]:
            component_id, expected = entries[0]
            findings.append(_finding(
                "fake_signature_mismatch", line,
                f"{name} takes {count} parameters; "
                f"the interface of {component_id} gives {expected}"))
    return findings


# --- R-PROBE-005 -----------------------------------------------------------

def _classify(testcases):
    findings = []
    reached = 0
    setup_reached = False
    for case in testcases:
        name = case.get("name")
        children = [c for c in case if c.tag in ("failure", "error")]
        messages = [(c.tag, c.get("message", "")) for c in children]
        undeclared = [m for _, m in messages
                      if "HotdocsProbeUndeclaredAsset" in m]
        if undeclared:
            findings.append(_finding("test_bug", None,
                                     f"{name}: {undeclared[0]}"))
            continue
        stub = [tag for tag, m in messages if "HotdocsProbeStubReached" in m]
        if stub:
            reached += 1
            if "error" in stub:
                setup_reached = True
            continue
        if setup_reached and ("error",
                              'failed on setup with "AssertionError"') \
                in messages:
            continue
        bugs = [m for tag, m in messages
                if tag == "error" or m.startswith(_BUG_PREFIXES)]
        if bugs:
            findings.append(_finding("test_bug", None, f"{name}: {bugs[0]}"))
            continue
        if not children and case.find("skipped") is None:
            findings.append(_finding(
                "vacuous", None,
                f"{name} passed without reaching the code under test",
                severity="warn"))
    return findings, reached


def _stub_run(test_source, module_names, timeout, interpreter, assets,
              drivers):
    tmp = tempfile.mkdtemp()
    try:
        files = {_TEST_FILE: test_source, _PLUGIN_FILE: _PLUGIN_SOURCE}
        for name in module_names:
            files[name + ".py"] = _STUB_SOURCE
        for file_name, source in files.items():
            with open(os.path.join(tmp, file_name), "w",
                      encoding="utf-8") as handle:
                handle.write(source)
        env = dict(os.environ)
        env["PYTHONPATH"] = tmp
        if assets is None:
            env.pop("HOTDOCS_PROBE_ASSETS", None)
        else:
            env["HOTDOCS_PROBE_ASSETS"] = json.dumps(assets)
        env["HOTDOCS_PROBE_DRIVERS"] = json.dumps(drivers or [])
        report_path = os.path.join(tmp, "report.xml")
        command = [interpreter or sys.executable, "-m", "pytest", "-q",
                   "-p", "no:cacheprovider", "--noconftest",
                   "-p", "hotdocs_probe_assets",
                   f"--junitxml={report_path}", _TEST_FILE]
        try:
            proc = subprocess.run(command, cwd=tmp, env=env,
                                  capture_output=True, text=True,
                                  timeout=timeout)
        except subprocess.TimeoutExpired:
            return [_finding("probe_timeout", None,
                             f"stub run exceeded {timeout} seconds")], 0, 0
        lines = [line for line in (proc.stdout + proc.stderr).splitlines()
                 if line.strip()]
        collection = [_finding("collection_error", None,
                               lines[-1] if lines else "")]
        if proc.returncode in (2, 3, 4):
            return collection, 0, 0
        testcases = list(ET.parse(report_path).getroot().iter("testcase"))
        if not testcases or any(
                c.tag == "error" and c.get("message") == "collection failure"
                for case in testcases for c in case):
            return collection, 0, 0
        findings, reached = _classify(testcases)
        return findings, len(testcases), reached
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# --- probe -----------------------------------------------------------------

def probe(test_source, criterion_bundle, module_name, *, timeout=60.0,
          interpreter=None, assets=None, drivers=None):
    try:
        tree = ast.parse(test_source)
    except SyntaxError as exc:
        return ProbeReport(ok=False,
                           findings=[_finding("syntax_error", exc.lineno,
                                              exc.msg)],
                           tests_run=0, tests_reached=0)

    module_names = [module_name] if isinstance(module_name, str) \
        else list(module_name)
    interfaces = _get(criterion_bundle, "dependency_interfaces", {})

    findings = []
    findings += _sorted(_check_pyflakes(test_source))
    findings += _sorted(_check_imports(tree, module_names, interpreter))
    findings += _sorted(_check_fakes(tree, interfaces))

    tests_run = 0
    tests_reached = 0
    if not any(f["severity"] == "error" for f in findings):
        stub_findings, tests_run, tests_reached = _stub_run(
            test_source, module_names, timeout, interpreter, assets, drivers)
        findings += _sorted(stub_findings)

    return ProbeReport(
        ok=not any(f["severity"] == "error" for f in findings),
        findings=findings,
        tests_run=tests_run,
        tests_reached=tests_reached,
    )
