"""Test probe: checks a generated test file for defects of its own."""

import ast
import importlib.util
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

GATE_VERSION = "test-probe@1.0.0"

_TARGET = "test_probe_target.py"

_SEVERITY = {
    "syntax_error": "error",
    "undefined_name": "error",
    "unknown_import": "error",
    "fake_signature_mismatch": "error",
    "collection_error": "error",
    "test_bug": "error",
    "probe_timeout": "error",
    "vacuous": "warn",
}

_BUG_PREFIXES = ("NameError", "UnboundLocalError", "ImportError", "ModuleNotFoundError")

_IMPORT_GUARDS = ("ImportError", "ModuleNotFoundError")

_SIG_START = re.compile(r"([A-Za-z_]\w*)\(")
_ARROW = re.compile(r"\s*->")

STUB_SOURCE = '''class HotdocsProbeStubReached(BaseException):
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
    return {"kind": kind, "severity": _SEVERITY[kind], "line": line, "message": message}


def _sorted(findings):
    return sorted(findings, key=lambda f: (f["line"], f["message"]))


def _report(findings, tests_run, tests_reached):
    ok = not any(f["severity"] == "error" for f in findings)
    return ProbeReport(ok, findings, tests_run, tests_reached)


# -- R-PROBE-002: pyflakes -------------------------------------------------


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
        _finding("undefined_name", m.lineno, "undefined name '%s'" % m.message_args[0])
        for m in collector.messages
        if isinstance(m, pyflakes.messages.UndefinedName)
    ]


# -- R-PROBE-003: imports --------------------------------------------------


def _guards_import(node):
    for handler in node.handlers:
        types = handler.type.elts if isinstance(handler.type, ast.Tuple) else [handler.type]
        if any(isinstance(t, ast.Name) and t.id in _IMPORT_GUARDS for t in types):
            return True
    return False


def _collect_imports(node, guarded, out):
    if isinstance(node, (ast.Import, ast.ImportFrom)) and not guarded:
        out.append(node)
    for name, value in ast.iter_fields(node):
        children = value if isinstance(value, list) else [value]
        child_guarded = guarded or (
            isinstance(node, ast.Try) and name == "body" and _guards_import(node)
        )
        for child in children:
            if isinstance(child, ast.AST):
                _collect_imports(child, child_guarded, out)


def _resolves(part, names):
    return (
        part in names
        or part in sys.stdlib_module_names
        or importlib.util.find_spec(part) is not None
    )


def _check_imports(tree, names):
    nodes = []
    _collect_imports(tree, False, nodes)
    findings = []
    for node in nodes:
        if isinstance(node, ast.Import):
            modules = [alias.name for alias in node.names]
        elif node.level == 0:
            modules = [node.module]
        else:
            modules = []
        for module in modules:
            part = module.split(".")[0]
            if not _resolves(part, names):
                findings.append(_finding("unknown_import", node.lineno, "cannot import '%s'" % part))
    return findings


# -- R-PROBE-004: fake arity -----------------------------------------------


def _arity(args):
    params = list(args.posonlyargs) + list(args.args) + list(args.kwonlyargs)
    params += [a for a in (args.vararg, args.kwarg) if a is not None]
    count = len([p for p in params if p.arg != "self"])
    return count, args.vararg is not None or args.kwarg is not None


def _signatures(text):
    for match in _SIG_START.finditer(text):
        depth = 0
        for index in range(match.end() - 1, len(text)):
            char = text[index]
            if char in "([{":
                depth += 1
            elif char in ")]}":
                depth -= 1
                if depth == 0:
                    break
        else:
            continue
        if not _ARROW.match(text, index + 1):
            continue
        name = match.group(1)
        try:
            tree = ast.parse("def %s(%s): pass" % (name, text[match.end():index]))
        except (SyntaxError, ValueError):
            continue
        yield name, _arity(tree.body[0].args)[0]


def _collect_fakes(module, offset, out):
    known = {}
    for node in module.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            count, variadic = _arity(node.args)
            known[node.name] = (count, variadic, node.lineno + offset)
            out.append((node.name,) + known[node.name])
        elif (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and isinstance(node.value, ast.Name)
            and node.value.id in known
        ):
            known[node.targets[0].id] = known[node.value.id]
            out.append((node.targets[0].id,) + known[node.value.id])


def _check_fakes(tree, dependency_interfaces):
    interfaces = {}
    for component_id, text in dependency_interfaces.items():
        for name, count in _signatures(text):
            interfaces.setdefault(name, []).append((component_id, count))
    fakes = []
    _collect_fakes(tree, 0, fakes)
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            try:
                inner = ast.parse(node.value)
            except (SyntaxError, ValueError):
                continue
            _collect_fakes(inner, node.lineno - 1, fakes)
    findings = []
    for name, count, variadic, line in fakes:
        if name not in interfaces or variadic:
            continue
        options = interfaces[name]
        if any(count == m for _, m in options):
            continue
        component_id, expected = options[0]
        findings.append(
            _finding(
                "fake_signature_mismatch",
                line,
                "%s takes %d parameters; the interface of %s gives %d"
                % (name, count, component_id, expected),
            )
        )
    return findings


# -- R-PROBE-005: stub run -------------------------------------------------


def _last_line(proc):
    out = proc.stdout.strip() or proc.stderr.strip()
    return (out.splitlines() or [""])[-1]


def _stub_run(test_source, names, timeout):
    tmp = tempfile.mkdtemp()
    try:
        with open(os.path.join(tmp, _TARGET), "w", encoding="utf-8") as handle:
            handle.write(test_source)
        for name in names:
            with open(os.path.join(tmp, name + ".py"), "w", encoding="utf-8") as handle:
                handle.write(STUB_SOURCE)
        report_path = os.path.join(tmp, "report.xml")
        env = dict(os.environ)
        env["PYTHONPATH"] = tmp
        command = [
            sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
            "--noconftest", "--junitxml=" + report_path, _TARGET,
        ]
        try:
            proc = subprocess.run(
                command, cwd=tmp, env=env, capture_output=True, text=True, timeout=timeout
            )
        except subprocess.TimeoutExpired:
            return [_finding("probe_timeout", None, "stub run exceeded %s seconds" % timeout)], 0, 0
        testcases = (
            list(ET.parse(report_path).getroot().iter("testcase"))
            if os.path.exists(report_path)
            else []
        )
        collection_failed = any(
            err.get("message", "") == "collection failure"
            for tc in testcases
            for err in tc.findall("error")
        )
        if proc.returncode in (2, 3, 4) or not testcases or collection_failed:
            return [_finding("collection_error", None, _last_line(proc))], 0, 0
        findings = []
        reached = 0
        for tc in testcases:
            name = tc.get("name", "")
            failure = tc.find("failure")
            error = tc.find("error")
            failure_message = None if failure is None else failure.get("message", "")
            if failure_message is not None and "HotdocsProbeStubReached" in failure_message:
                reached += 1
            elif error is not None:
                findings.append(_finding("test_bug", None, "%s: %s" % (name, error.get("message", ""))))
            elif failure_message is not None and failure_message.startswith(_BUG_PREFIXES):
                findings.append(_finding("test_bug", None, "%s: %s" % (name, failure_message)))
            elif failure is None and tc.find("skipped") is None:
                findings.append(
                    _finding("vacuous", None, "%s passed without reaching the code under test" % name)
                )
        return findings, len(testcases), reached
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# -- entry point -----------------------------------------------------------


def _dependency_interfaces(criterion_bundle):
    if isinstance(criterion_bundle, Mapping):
        return criterion_bundle.get("dependency_interfaces", {})
    return getattr(criterion_bundle, "dependency_interfaces", {})


def probe(test_source, criterion_bundle, module_name, *, timeout=60.0):
    names = [module_name] if isinstance(module_name, str) else list(module_name)
    try:
        tree = ast.parse(test_source)
    except SyntaxError as exc:
        return _report([_finding("syntax_error", exc.lineno, str(exc.msg))], 0, 0)

    findings = []
    findings += _sorted(_check_pyflakes(test_source))
    findings += _sorted(_check_imports(tree, names))
    findings += _sorted(_check_fakes(tree, _dependency_interfaces(criterion_bundle)))

    if any(f["severity"] == "error" for f in findings):
        return _report(findings, 0, 0)

    run_findings, tests_run, tests_reached = _stub_run(test_source, names, timeout)
    findings += _sorted(run_findings)
    return _report(findings, tests_run, tests_reached)
