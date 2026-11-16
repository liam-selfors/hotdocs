"""Test probe: checks a generated test file for defects of its own."""

import ast
import dataclasses
import importlib.util
import io
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
import pyflakes.reporter

GATE_VERSION = "test-probe@1.0.0"

_TARGET_NAME = "test_probe_target.py"

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

_TEST_BUG_PREFIXES = (
    "NameError",
    "UnboundLocalError",
    "ImportError",
    "ModuleNotFoundError",
)

_IMPORT_ERROR_NAMES = ("ImportError", "ModuleNotFoundError")

_SIG_START = re.compile(r"(?<!\w)([A-Za-z_]\w*)\(")
_ARROW = re.compile(r"\s*->")


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


def _finding(kind, line, message):
    return {
        "kind": kind,
        "severity": "warn" if kind == "vacuous" else "error",
        "line": line,
        "message": message,
    }


def _ordered(findings):
    return sorted(findings, key=lambda f: (f["line"], f["message"]))


# --- R-PROBE-002: pyflakes -------------------------------------------------


class _CollectingReporter(pyflakes.reporter.Reporter):
    def __init__(self):
        super().__init__(io.StringIO(), io.StringIO())
        self.messages = []

    def flake(self, message):
        self.messages.append(message)


def _check_undefined_names(test_source):
    reporter = _CollectingReporter()
    pyflakes.api.check(test_source, _TARGET_NAME, reporter)
    findings = []
    for message in reporter.messages:
        if isinstance(message, pyflakes.messages.UndefinedName):
            findings.append(
                _finding(
                    "undefined_name",
                    message.lineno,
                    "undefined name '%s'" % message.message_args[0],
                )
            )
    return _ordered(findings)


# --- R-PROBE-003: imports ----------------------------------------------------


def _catches_import_error(try_node):
    for handler in try_node.handlers:
        caught = handler.type
        elts = caught.elts if isinstance(caught, ast.Tuple) else [caught]
        if any(
            isinstance(e, ast.Name) and e.id in _IMPORT_ERROR_NAMES for e in elts
        ):
            return True
    return False


def _unresolved(part, module_name):
    return (
        part != module_name
        and part not in sys.stdlib_module_names
        and importlib.util.find_spec(part) is None
    )


def _visit_imports(node, guarded, module_name, out):
    if isinstance(node, ast.Try):
        inner = guarded or _catches_import_error(node)
        for child in node.body:
            _visit_imports(child, inner, module_name, out)
        for child in node.handlers + node.orelse + node.finalbody:
            _visit_imports(child, guarded, module_name, out)
        return
    if not guarded:
        parts = []
        if isinstance(node, ast.Import):
            parts = [alias.name.split(".")[0] for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.level == 0:
            parts = [node.module.split(".")[0]]
        for part in parts:
            if _unresolved(part, module_name):
                out.append(
                    _finding("unknown_import", node.lineno, "cannot import '%s'" % part)
                )
    for child in ast.iter_child_nodes(node):
        _visit_imports(child, guarded, module_name, out)


def _check_imports(tree, module_name):
    findings = []
    _visit_imports(tree, False, module_name, findings)
    return _ordered(findings)


# --- R-PROBE-004: fake arity -------------------------------------------------


def _interface_signatures(text):
    """Yield (name, parameter count) for each parseable signature in text."""
    for match in _SIG_START.finditer(text):
        start = match.end() - 1
        depth = 0
        end = None
        for index in range(start, len(text)):
            char = text[index]
            if char in "([{":
                depth += 1
            elif char in ")]}":
                depth -= 1
                if depth == 0:
                    end = index
                    break
        if end is None or text[end] != ")" or not _ARROW.match(text, end + 1):
            continue
        params = text[start + 1:end]
        try:
            fn = ast.parse("def _f(%s):\n    pass\n" % params).body[0]
        except SyntaxError:
            continue
        args = fn.args
        names = [a.arg for a in args.posonlyargs + args.args + args.kwonlyargs]
        names += [a.arg for a in (args.vararg, args.kwarg) if a is not None]
        yield match.group(1), sum(1 for n in names if n != "self")


def _fake_arity(args):
    if args.vararg is not None or args.kwarg is not None:
        return None
    return len(args.posonlyargs) + len(args.args) + len(args.kwonlyargs)


def _collect_fakes(tree):
    defs = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            defs.append((node.name, _fake_arity(node.args), node.lineno))
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            try:
                inner = ast.parse(node.value)
            except (SyntaxError, ValueError):
                continue
            for sub in inner.body:
                if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    defs.append(
                        (sub.name, _fake_arity(sub.args), node.lineno + sub.lineno - 1)
                    )
    by_name = {name: (count, line) for name, count, line in defs}
    fakes = list(defs)
    for node in tree.body:
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and isinstance(node.value, ast.Name)
            and node.value.id in by_name
        ):
            count, line = by_name[node.value.id]
            fakes.append((node.targets[0].id, count, line))
    return fakes


def _dependency_interfaces(criterion_bundle):
    if isinstance(criterion_bundle, Mapping):
        return criterion_bundle.get("dependency_interfaces", {})
    return getattr(criterion_bundle, "dependency_interfaces", {})


def _check_fakes(tree, criterion_bundle):
    deps = {}
    for component_id, text in _dependency_interfaces(criterion_bundle).items():
        for name, count in _interface_signatures(text):
            deps.setdefault(name, []).append((component_id, count))
    findings = []
    for name, count, line in _collect_fakes(tree):
        if name not in deps or count is None:
            continue
        signatures = deps[name]
        if any(m == count for _, m in signatures):
            continue
        component_id, m = signatures[0]
        findings.append(
            _finding(
                "fake_signature_mismatch",
                line,
                "%s takes %d parameters; the interface of %s gives %d"
                % (name, count, component_id, m),
            )
        )
    return _ordered(findings)


# --- R-PROBE-005: stub run ---------------------------------------------------


def _stub_run(test_source, module_name, timeout):
    """Return (findings, tests_run, tests_reached)."""
    tmp = tempfile.mkdtemp()
    try:
        with open(os.path.join(tmp, _TARGET_NAME), "w", encoding="utf-8") as fh:
            fh.write(test_source)
        with open(os.path.join(tmp, module_name + ".py"), "w", encoding="utf-8") as fh:
            fh.write(_STUB_SOURCE)
        report_path = os.path.join(tmp, "report.xml")
        env = dict(os.environ)
        env["PYTHONPATH"] = tmp
        command = [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
            "--noconftest",
            "--junitxml=" + report_path,
            _TARGET_NAME,
        ]
        try:
            result = subprocess.run(
                command,
                cwd=tmp,
                env=env,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            return (
                [
                    _finding(
                        "probe_timeout",
                        None,
                        "stub run exceeded %s seconds" % timeout,
                    )
                ],
                0,
                0,
            )
        last_line = ((result.stdout + result.stderr).strip().splitlines() or [""])[-1]
        collection_error = (
            [_finding("collection_error", None, last_line)],
            0,
            0,
        )
        if result.returncode in (2, 3, 4):
            return collection_error
        root = ET.parse(report_path).getroot()
        testcases = []
        collection_failed = False
        for testcase in root.iter("testcase"):
            error = testcase.find("error")
            if error is not None and error.get("message") == "collection failure":
                collection_failed = True
            else:
                testcases.append(testcase)
        if collection_failed or not testcases:
            return collection_error
        findings = []
        reached = 0
        for testcase in testcases:
            name = testcase.get("name")
            failure = testcase.find("failure")
            error = testcase.find("error")
            skipped = testcase.find("skipped")
            if failure is not None:
                message = failure.get("message", "")
                if "HotdocsProbeStubReached" in message:
                    reached += 1
                elif message.startswith(_TEST_BUG_PREFIXES):
                    findings.append(
                        _finding("test_bug", None, "%s: %s" % (name, message))
                    )
            if error is not None:
                findings.append(
                    _finding(
                        "test_bug", None, "%s: %s" % (name, error.get("message", ""))
                    )
                )
            if failure is None and error is None and skipped is None:
                findings.append(
                    _finding(
                        "vacuous",
                        None,
                        "%s passed without reaching the code under test" % name,
                    )
                )
        return _ordered(findings), len(testcases), reached
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# --- probe -------------------------------------------------------------------


def probe(test_source, criterion_bundle, module_name, *, timeout=60.0):
    try:
        tree = ast.parse(test_source)
    except SyntaxError as exc:
        return ProbeReport(
            ok=False,
            findings=[_finding("syntax_error", exc.lineno, exc.msg)],
            tests_run=0,
            tests_reached=0,
        )
    findings = []
    findings += _check_undefined_names(test_source)
    findings += _check_imports(tree, module_name)
    findings += _check_fakes(tree, criterion_bundle)
    tests_run = 0
    tests_reached = 0
    if not any(f["severity"] == "error" for f in findings):
        stub_findings, tests_run, tests_reached = _stub_run(
            test_source, module_name, timeout
        )
        findings += stub_findings
    return ProbeReport(
        ok=not any(f["severity"] == "error" for f in findings),
        findings=findings,
        tests_run=tests_run,
        tests_reached=tests_reached,
    )
