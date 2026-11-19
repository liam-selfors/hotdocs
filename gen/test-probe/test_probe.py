"""Test probe: checks a generated test file for defects of its own."""

import ast
import importlib.util
import os
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
import xml.etree.ElementTree as ET
from collections.abc import Mapping
from dataclasses import dataclass, field

import pyflakes.api
import pyflakes.messages

GATE_VERSION = "test-probe@1.1.0"

_TEST_FILENAME = "test_probe_target.py"

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

_BUG_PREFIXES = ("NameError", "UnboundLocalError", "ImportError", "ModuleNotFoundError")
_IMPORT_ERRORS = {"ImportError", "ModuleNotFoundError"}

_SIG_START = re.compile(r"(?<!\w)([A-Za-z_]\w*)\(")
_ARROW = re.compile(r"\s*->")


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
    return {"kind": kind, "severity": severity, "line": line, "message": message}


def _build_report(findings, tests_run, tests_reached):
    ordered = sorted(
        findings,
        key=lambda f: (
            _CHECK_ORDER[f["kind"]],
            f["line"] is None,
            f["line"] or 0,
            f["message"],
        ),
    )
    ok = not any(f["severity"] == "error" for f in ordered)
    return ProbeReport(ok=ok, findings=ordered, tests_run=tests_run, tests_reached=tests_reached)


class _Reporter:
    def __init__(self):
        self.messages = []

    def flake(self, message):
        self.messages.append(message)

    def syntaxError(self, filename, msg, lineno, offset, text):
        pass

    def unexpectedError(self, filename, msg):
        pass


def _check_pyflakes(test_source):
    reporter = _Reporter()
    pyflakes.api.check(test_source, _TEST_FILENAME, reporter)
    return [
        _finding("undefined_name", m.lineno, "undefined name '%s'" % m.message_args[0])
        for m in reporter.messages
        if isinstance(m, pyflakes.messages.UndefinedName)
    ]


def _handler_names(handler_type):
    if isinstance(handler_type, ast.Tuple):
        nodes = handler_type.elts
    else:
        nodes = [handler_type]
    names = set()
    for node in nodes:
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
    return names


def _protected_imports(tree):
    protected = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Try) and any(
            h.type is not None and _handler_names(h.type) & _IMPORT_ERRORS
            for h in node.handlers
        ):
            for stmt in node.body:
                for inner in ast.walk(stmt):
                    protected.add(id(inner))
    return protected


def _check_imports(tree, names):
    protected = _protected_imports(tree)
    findings = []
    for node in ast.walk(tree):
        if id(node) in protected:
            continue
        if isinstance(node, ast.Import):
            modules = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.level == 0:
            modules = [node.module]
        else:
            continue
        for module in modules:
            part = module.split(".")[0]
            if (
                part not in names
                and part not in sys.stdlib_module_names
                and importlib.util.find_spec(part) is None
            ):
                findings.append(_finding("unknown_import", node.lineno, "cannot import '%s'" % part))
    return findings


def _parse_signatures(text):
    sigs = []
    for match in _SIG_START.finditer(text):
        depth = 1
        i = match.end()
        start = i
        params = []
        while i < len(text) and depth:
            char = text[i]
            if char in "([{":
                depth += 1
            elif char in ")]}":
                depth -= 1
            elif char == "," and depth == 1:
                params.append(text[start:i])
                start = i + 1
            i += 1
        if depth:
            continue
        params.append(text[start:i - 1])
        if not _ARROW.match(text, i):
            continue
        count = sum(1 for p in params if p.strip() not in ("", "*", "/", "self"))
        sigs.append((match.group(1), count))
    return sigs


def _dependency_interfaces(criterion_bundle):
    if isinstance(criterion_bundle, Mapping):
        return criterion_bundle.get("dependency_interfaces", {})
    return getattr(criterion_bundle, "dependency_interfaces", {})


def _check_fakes(tree, criterion_bundle):
    signatures = {}
    for component_id, text in _dependency_interfaces(criterion_bundle).items():
        for name, count in _parse_signatures(text):
            signatures.setdefault(name, []).append((component_id, count))

    fakes = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            try:
                inner = ast.parse(textwrap.dedent(node.value))
            except (SyntaxError, ValueError):
                continue
            for stmt in inner.body:
                if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)) and stmt.name in signatures:
                    fakes.append((stmt.name, stmt, node.lineno + stmt.lineno - 1))

    resolve = {}
    for stmt in tree.body:
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
            resolve[stmt.name] = stmt
        elif (
            isinstance(stmt, ast.Assign)
            and len(stmt.targets) == 1
            and isinstance(stmt.targets[0], ast.Name)
            and isinstance(stmt.value, ast.Name)
            and stmt.value.id in resolve
        ):
            resolve[stmt.targets[0].id] = resolve[stmt.value.id]

    for node in ast.walk(tree):
        installed = None
        if (
            isinstance(node, ast.Call)
            and (
                (isinstance(node.func, ast.Name) and node.func.id == "setattr")
                or (isinstance(node.func, ast.Attribute) and node.func.attr == "setattr")
            )
            and len(node.args) == 3
            and isinstance(node.args[1], ast.Constant)
            and isinstance(node.args[1].value, str)
            and isinstance(node.args[2], ast.Name)
        ):
            installed = (node.args[1].value, node.args[2].id)
        elif (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Attribute)
            and isinstance(node.value, ast.Name)
        ):
            installed = (node.targets[0].attr, node.value.id)
        if installed and installed[0] in signatures and installed[1] in resolve:
            fn = resolve[installed[1]]
            fakes.append((installed[0], fn, fn.lineno))

    findings = set()
    for name, fn, line in fakes:
        args = fn.args
        if args.vararg is not None or args.kwarg is not None:
            continue
        n = len(args.posonlyargs) + len(args.args) + len(args.kwonlyargs)
        candidates = signatures[name]
        if any(count == n for _, count in candidates):
            continue
        component_id, m = candidates[0]
        findings.add(
            (line, "%s takes %d parameters; the interface of %s gives %d" % (name, n, component_id, m))
        )
    return [_finding("fake_signature_mismatch", line, message) for line, message in findings]


def _stub_run(test_source, names, timeout):
    tmp = tempfile.mkdtemp()
    try:
        with open(os.path.join(tmp, _TEST_FILENAME), "w", encoding="utf-8") as fh:
            fh.write(test_source)
        for name in names:
            with open(os.path.join(tmp, name + ".py"), "w", encoding="utf-8") as fh:
                fh.write(_STUB_SOURCE)
        report_path = os.path.join(tmp, "report.xml")
        cmd = [
            sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "--noconftest",
            "--junitxml=" + report_path, _TEST_FILENAME,
        ]
        env = dict(os.environ, PYTHONPATH=tmp)
        try:
            proc = subprocess.run(
                cmd, cwd=tmp, env=env, capture_output=True, text=True, timeout=timeout
            )
        except subprocess.TimeoutExpired:
            return [_finding("probe_timeout", None, "stub run exceeded %s seconds" % timeout)], 0, 0

        testcases = []
        if os.path.exists(report_path):
            testcases = list(ET.parse(report_path).getroot().iter("testcase"))

        real = []
        collection_failed = False
        for case in testcases:
            if any(e.get("message") == "collection failure" for e in case.findall("error")):
                collection_failed = True
            else:
                real.append(case)

        if collection_failed or not testcases or proc.returncode in (2, 3, 4):
            lines = (proc.stdout + proc.stderr).strip().splitlines()
            last = lines[-1].strip() if lines else ""
            return [_finding("collection_error", None, last)], 0, 0

        findings = []
        reached = 0
        for case in real:
            name = case.get("name", "")
            failure = case.find("failure")
            errors = case.findall("error")
            if failure is not None:
                message = failure.get("message", "")
                if "HotdocsProbeStubReached" in message:
                    reached += 1
                elif message.startswith(_BUG_PREFIXES):
                    findings.append(_finding("test_bug", None, "%s: %s" % (name, message)))
            for error in errors:
                findings.append(_finding("test_bug", None, "%s: %s" % (name, error.get("message", ""))))
            if failure is None and not errors and case.find("skipped") is None:
                findings.append(
                    _finding(
                        "vacuous",
                        None,
                        "%s passed without reaching the code under test" % name,
                        severity="warn",
                    )
                )
        return findings, len(real), reached
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def probe(test_source, criterion_bundle, module_name, *, timeout=60.0):
    names = [module_name] if isinstance(module_name, str) else list(module_name)

    try:
        tree = ast.parse(test_source)
    except SyntaxError as exc:
        return _build_report([_finding("syntax_error", exc.lineno, str(exc.msg))], 0, 0)

    findings = []
    findings.extend(_check_pyflakes(test_source))
    findings.extend(_check_imports(tree, names))
    findings.extend(_check_fakes(tree, criterion_bundle))

    if any(f["severity"] == "error" for f in findings):
        return _build_report(findings, 0, 0)

    stub_findings, tests_run, tests_reached = _stub_run(test_source, names, timeout)
    findings.extend(stub_findings)
    return _build_report(findings, tests_run, tests_reached)
