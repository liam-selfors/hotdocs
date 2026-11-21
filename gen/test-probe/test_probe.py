"""Test probe: checks a generated test file for defects of its own."""

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
from dataclasses import dataclass, field

import pyflakes.api
import pyflakes.messages

GATE_VERSION = "test-probe@1.3.0"

_TARGET = "test_probe_target.py"
_STUB_NAME = "HotdocsProbeStubReached"
_SETUP_ASSERTION = 'failed on setup with "AssertionError"'
_BUG_PREFIXES = ("NameError", "UnboundLocalError", "ImportError", "ModuleNotFoundError")
_IMPORT_ERRORS = {"ImportError", "ModuleNotFoundError"}
_TRY_TYPES = tuple({ast.Try, getattr(ast, "TryStar", ast.Try)})

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

ASSET_PLUGIN_SOURCE = '''import pytest


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
    return sorted(findings, key=lambda f: (f["line"] is None, f["line"] or 0, f["message"]))


def _read(obj, key, default):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


# --- R-PROBE-002 -----------------------------------------------------------

class _Reporter:
    def __init__(self):
        self.messages = []

    def flake(self, message):
        self.messages.append(message)

    def syntaxError(self, *args, **kwargs):
        pass

    def unexpectedError(self, *args, **kwargs):
        pass


def _check_pyflakes(test_source):
    reporter = _Reporter()
    pyflakes.api.check(test_source, _TARGET, reporter)
    out = []
    for msg in reporter.messages:
        if isinstance(msg, pyflakes.messages.UndefinedName):
            out.append(_finding("undefined_name", msg.lineno,
                                "undefined name '%s'" % msg.message_args[0]))
    return _sorted(out)


# --- R-PROBE-003 -----------------------------------------------------------

def _names_import_error(node):
    if isinstance(node, ast.Name):
        return node.id in _IMPORT_ERRORS
    if isinstance(node, ast.Tuple):
        return any(_names_import_error(e) for e in node.elts)
    return False


def _collect_imports(tree):
    out = []

    def visit(node, guarded):
        if isinstance(node, (ast.Import, ast.ImportFrom)) and not guarded:
            out.append(node)
        if isinstance(node, _TRY_TYPES):
            inner = guarded or any(_names_import_error(h.type) for h in node.handlers)
            for child in node.body:
                visit(child, inner)
            for child in list(node.handlers) + node.orelse + node.finalbody:
                visit(child, guarded)
            return
        for child in ast.iter_child_nodes(node):
            visit(child, guarded)

    visit(tree, False)
    return out


_FIND_SPEC_SCRIPT = (
    "import importlib.util, json, sys\n"
    "print(json.dumps([p for p in sys.argv[1:] "
    "if importlib.util.find_spec(p) is None]))\n"
)


def _unresolved(parts, interpreter):
    if interpreter is None:
        return {p for p in parts if importlib.util.find_spec(p) is None}
    if not parts:
        return set()
    proc = subprocess.run(
        [interpreter, "-c", _FIND_SPEC_SCRIPT] + sorted(parts),
        capture_output=True, text=True, env=os.environ.copy(),
    )
    return set(json.loads(proc.stdout.strip().splitlines()[-1]))


def _check_imports(tree, module_names, interpreter):
    pending = []
    for node in _collect_imports(tree):
        if isinstance(node, ast.ImportFrom):
            if node.level:
                continue
            parts = [node.module.split(".")[0]]
        else:
            parts = [alias.name.split(".")[0] for alias in node.names]
        for part in dict.fromkeys(parts):
            if part in module_names or part in sys.stdlib_module_names:
                continue
            pending.append((node.lineno, part))
    missing = _unresolved({p for _, p in pending}, interpreter)
    out = [_finding("unknown_import", line, "cannot import '%s'" % part)
           for line, part in pending if part in missing]
    return _sorted(out)


# --- R-PROBE-004 -----------------------------------------------------------

def _arguments(params):
    try:
        tree = ast.parse("def _f(%s):\n    pass\n" % params)
    except SyntaxError:
        return None
    return tree.body[0].args


def _named_count(args):
    names = [a.arg for a in args.posonlyargs + args.args + args.kwonlyargs]
    return len([n for n in names if n != "self"])


def _signatures(text):
    for match in re.finditer(r"([A-Za-z_]\w*)\(", text):
        start = match.end()
        depth = 0
        i = start
        end = None
        while i < len(text):
            ch = text[i]
            if ch in "([{":
                depth += 1
            elif ch in ")]}":
                if depth == 0:
                    end = i
                    break
                depth -= 1
            i += 1
        if end is None or not re.match(r"\s*->", text[end + 1:]):
            continue
        args = _arguments(text[start:end])
        if args is None:
            continue
        count = _named_count(args) + (args.vararg is not None) + (args.kwarg is not None)
        yield match.group(1), count


def _interface_signatures(dep_interfaces):
    sigs = {}
    for cid, text in dep_interfaces.items():
        for name, count in _signatures(text):
            sigs.setdefault(name, []).append((cid, count))
    return sigs


def _fake_finding(name, fn, line, sigs):
    args = fn.args
    if args.vararg is not None or args.kwarg is not None:
        return None
    n = _named_count(args)
    candidates = sigs[name]
    if any(m == n for _, m in candidates):
        return None
    cid, m = candidates[0]
    return _finding("fake_signature_mismatch", line,
                    "%s takes %d parameters; the interface of %s gives %d" % (name, n, cid, m))


def _check_fakes(tree, dep_interfaces):
    sigs = _interface_signatures(dep_interfaces)
    fakes = []  # (name, def node, line)

    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            try:
                inner = ast.parse(node.value)
            except (SyntaxError, ValueError):
                continue
            for stmt in inner.body:
                if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)) and stmt.name in sigs:
                    fakes.append((stmt.name, stmt, node.lineno + stmt.lineno - 1))

    defs = {}
    aliases = {}
    for stmt in tree.body:
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
            defs[stmt.name] = stmt
        elif (isinstance(stmt, ast.Assign) and len(stmt.targets) == 1
              and isinstance(stmt.targets[0], ast.Name) and isinstance(stmt.value, ast.Name)):
            aliases[stmt.targets[0].id] = stmt.value.id

    def resolve(name):
        seen = set()
        while name not in defs and name in aliases and name not in seen:
            seen.add(name)
            name = aliases[name]
        return defs.get(name)

    installs = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            is_setattr = ((isinstance(func, ast.Name) and func.id == "setattr")
                          or (isinstance(func, ast.Attribute) and func.attr == "setattr"))
            if (is_setattr and len(node.args) == 3
                    and isinstance(node.args[1], ast.Constant) and isinstance(node.args[1].value, str)
                    and isinstance(node.args[2], ast.Name)):
                installs.append((node.args[1].value, node.args[2].id))
        elif isinstance(node, ast.Assign) and isinstance(node.value, ast.Name):
            for target in node.targets:
                if isinstance(target, ast.Attribute):
                    installs.append((target.attr, node.value.id))

    for name, fn_name in installs:
        fn = resolve(fn_name)
        if fn is not None and name in sigs:
            fakes.append((name, fn, fn.lineno))

    out = {}
    for name, fn, line in fakes:
        finding = _fake_finding(name, fn, line, sigs)
        if finding is not None:
            out[(finding["line"], finding["message"])] = finding
    return _sorted(out.values())


# --- R-PROBE-005 / R-PROBE-007 ---------------------------------------------

def _last_line(proc_out):
    lines = [line.strip() for line in proc_out.splitlines() if line.strip()]
    return lines[-1] if lines else ""


def _stub_run(test_source, module_names, timeout, interpreter):
    tmp = tempfile.mkdtemp()
    try:
        with open(os.path.join(tmp, _TARGET), "w", encoding="utf-8") as fh:
            fh.write(test_source)
        for name in module_names:
            with open(os.path.join(tmp, name + ".py"), "w", encoding="utf-8") as fh:
                fh.write(STUB_SOURCE)
        with open(os.path.join(tmp, "hotdocs_probe_assets.py"), "w", encoding="utf-8") as fh:
            fh.write(ASSET_PLUGIN_SOURCE)
        report_path = os.path.join(tmp, "report.xml")
        env = os.environ.copy()
        env["PYTHONPATH"] = tmp
        cmd = [interpreter, "-m", "pytest", "-q", "-p", "no:cacheprovider", "--noconftest",
               "-p", "hotdocs_probe_assets", "--junitxml=" + report_path, _TARGET]
        try:
            proc = subprocess.run(cmd, cwd=tmp, env=env, capture_output=True, text=True,
                                  stdin=subprocess.DEVNULL, timeout=timeout)
        except subprocess.TimeoutExpired:
            return [_finding("probe_timeout", None,
                             "stub run exceeded %s seconds" % timeout)], 0, 0
        output = (proc.stdout or "") + "\n" + (proc.stderr or "")
        testcases = []
        if os.path.exists(report_path):
            testcases = list(ET.parse(report_path).getroot().iter("testcase"))
        collection = [tc for tc in testcases
                      if any(c.tag == "error" and c.get("message") == "collection failure"
                             for c in tc)]
        real = [tc for tc in testcases if tc not in collection]
        if collection or not real or proc.returncode in (2, 3, 4):
            return [_finding("collection_error", None, _last_line(output))], 0, 0
        return _classify(real)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _classify(testcases):
    findings = []
    reached = 0
    setup_reached = False
    for tc in testcases:
        name = tc.get("name") or ""
        fails = [c for c in tc if c.tag in ("failure", "error")]
        if any(_STUB_NAME in (c.get("message") or "") for c in fails):
            reached += 1
            if any(c.tag == "error" and _STUB_NAME in (c.get("message") or "") for c in fails):
                setup_reached = True
            continue
        if not fails:
            if not any(c.tag == "skipped" for c in tc):
                findings.append(_finding(
                    "vacuous", None,
                    "%s passed without reaching the code under test" % name))
            continue
        for child in fails:
            message = child.get("message") or ""
            if child.tag == "error":
                if message == _SETUP_ASSERTION and setup_reached:
                    continue
                findings.append(_finding("test_bug", None, "%s: %s" % (name, message)))
                break
            if message.startswith(_BUG_PREFIXES):
                findings.append(_finding("test_bug", None, "%s: %s" % (name, message)))
                break
    return _sorted(findings), len(testcases), reached


# --- probe -----------------------------------------------------------------

def probe(test_source, criterion_bundle, module_name, *, timeout=60.0, interpreter=None):
    module_names = [module_name] if isinstance(module_name, str) else list(module_name)
    interp = sys.executable if interpreter is None else interpreter

    try:
        tree = ast.parse(test_source)
    except SyntaxError as exc:
        findings = [_finding("syntax_error", exc.lineno, str(exc.msg))]
        return ProbeReport(ok=False, findings=findings, tests_run=0, tests_reached=0)

    dep_interfaces = _read(criterion_bundle, "dependency_interfaces", {})

    findings = []
    findings += _check_pyflakes(test_source)
    findings += _check_imports(tree, set(module_names), interpreter)
    findings += _check_fakes(tree, dep_interfaces)

    tests_run = 0
    tests_reached = 0
    if not any(f["severity"] == "error" for f in findings):
        run_findings, tests_run, tests_reached = _stub_run(
            test_source, module_names, timeout, interp)
        findings += run_findings

    ok = not any(f["severity"] == "error" for f in findings)
    return ProbeReport(ok=ok, findings=findings, tests_run=tests_run, tests_reached=tests_reached)
