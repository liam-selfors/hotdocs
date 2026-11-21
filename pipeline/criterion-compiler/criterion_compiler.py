"""Criterion compiler: deterministic Given/When/Then -> pytest compilation.

No model, network, or code evaluation is involved at any stage. Work is split
into a target-independent parse+bind phase and a pytest emit phase
(R-COMPILE-011).
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from json.decoder import scanstring
from pathlib import Path

GATE_VERSION = "criterion-compiler@1.0.0"


@dataclass
class ParsedCriterion:
    criterion_id: str
    covers: str
    kind: str
    gherkin: str
    file: str


@dataclass
class InterfaceSurface:
    functions: dict = field(default_factory=dict)
    types: dict = field(default_factory=dict)
    module_name: str = ""


@dataclass
class CompileReport:
    outputs: list
    gate_version: str
    summary: dict


class _CompileError(Exception):
    def __init__(self, line, text):
        super().__init__(f"line {line}: {text}")


class _LitError(Exception):
    def __init__(self, text="", suffix=""):
        super().__init__(text)
        self.text = text
        self.suffix = suffix


# ---------------------------------------------------------------------------
# Literal parsing (data only, never evaluated)
# ---------------------------------------------------------------------------

_IDENT_RX = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_NUMBER_RX = re.compile(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?")
_ACCESS_RX = re.compile(r"(?:\.[A-Za-z0-9_]*|\[[^\]]*\])+")
_WS_RX = re.compile(r"\s*")
_CONSTANTS = {"true": True, "false": False, "null": None}


def _skip(s, i):
    return _WS_RX.match(s, i).end()


def _string(s, i):
    if s[i:i + 1] != '"':
        raise _LitError()
    try:
        return scanstring(s, i + 1)
    except ValueError:
        raise _LitError() from None


def _sequence(s, i, close, item):
    items = []
    i = _skip(s, i)
    if s[i:i + 1] == close:
        return items, i + 1
    while True:
        node, i = item(s, i)
        items.append(node)
        i = _skip(s, i)
        sep = s[i:i + 1]
        if sep == close:
            return items, i + 1
        if sep != ",":
            raise _LitError()
        i += 1


def _member(s, i):
    key, i = _string(s, _skip(s, i))
    i = _skip(s, i)
    if s[i:i + 1] != ":":
        raise _LitError()
    node, i = _value(s, i + 1)
    return (key, node), i


def _value(s, i):
    i = _skip(s, i)
    head = s[i:i + 1]
    if head == '"':
        text, end = _string(s, i)
        return ("lit", text), end
    if head == "{":
        items, end = _sequence(s, i + 1, "}", _member)
        return ("obj", items), end
    if head == "[":
        items, end = _sequence(s, i + 1, "]", _value)
        return ("arr", items), end
    number = _NUMBER_RX.match(s, i)
    if number:
        return ("lit", json.loads(number.group())), number.end()
    ident = _IDENT_RX.match(s, i)
    if ident is None:
        raise _LitError()
    name = ident.group()
    if name in _CONSTANTS:
        return ("lit", _CONSTANTS[name]), ident.end()
    access = _ACCESS_RX.match(s, ident.end())
    if access:
        raise _LitError(name + access.group(), " (field/index access)")
    return ("ref", name), ident.end()


def _lit_error(line, err, text):
    return _CompileError(line, f"'{err.text or text.strip()}' is not a literal{err.suffix}")


def _whole(text, line):
    try:
        node, i = _value(text, 0)
        if _skip(text, i) != len(text):
            raise _LitError()
    except _LitError as err:
        raise _lit_error(line, err, text) from None
    return node


def _resolve(node, bindings, line):
    tag, val = node
    if tag == "obj":
        return ("obj", [(k, _resolve(v, bindings, line)) for k, v in val])
    if tag == "arr":
        return ("arr", [_resolve(v, bindings, line) for v in val])
    if tag == "ref":
        if val not in bindings:
            raise _CompileError(line, f"unresolved reference '{val}'")
        return bindings[val]
    return node


# ---------------------------------------------------------------------------
# Parse + bind (target-independent)
# ---------------------------------------------------------------------------

_STEP_START_RX = re.compile(r"(?:Given|When|Then) ")
_STEP_RX = re.compile(r"(?:(Given|When|Then) )?(.*)", re.S)
_FIELD_RX = re.compile(r"\s*([A-Za-z_][A-Za-z0-9_]*)\s*:\s*")
_PATH = r'[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*|\[(?:-?[0-9]+|"[^"\\]*")\])*'


def _steps(gherkin):
    steps = []
    current = None
    for number, raw in enumerate(gherkin.splitlines(), 1):
        text = raw.strip()
        if not text:
            current = None
        elif current is None or _STEP_START_RX.match(text):
            current = [number, text]
            steps.append(current)
        else:
            current[1] += " " + text
    return steps


def _snake(name):
    name = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", name)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", name).lower()


def _unmatched(line, text):
    return _CompileError(line, f"step '{text}' does not match any recognized template")


class _Binder:
    def __init__(self, surface):
        self.surface = surface
        self.bindings = {}


def _given_fixture(st, line, text, m):
    node = _resolve(_whole(m.group(2), line), st.bindings, line)
    st.bindings[m.group(1)] = node
    return ("bind", m.group(1), node)


def _given_type(st, line, text, m):
    type_name, rest = m.group(1), m.group(2)
    if type_name not in st.surface.types:
        raise _CompileError(line, f"type '{type_name}' does not resolve")
    declared = st.surface.types[type_name]
    args = []
    i = 0
    while True:
        fm = _FIELD_RX.match(rest, i)
        if fm is None:
            raise _unmatched(line, text)
        fname = fm.group(1)
        if fname not in declared:
            raise _CompileError(line, f"field '{fname}' does not resolve")
        try:
            node, i = _value(rest, fm.end())
            i = _skip(rest, i)
            if i < len(rest) and rest[i] != ",":
                raise _LitError()
        except _LitError as err:
            raise _lit_error(line, err, rest[fm.end():]) from None
        args.append((fname, _resolve(node, st.bindings, line)))
        if i == len(rest):
            break
        i += 1
    var = _snake(type_name)
    st.bindings[var] = ("var", var)
    return ("construct", var, type_name, args)


def _when_endpoint(st, line, text, m):
    raise _CompileError(line, f"endpoint '{m.group(1)} {m.group(2)}' does not resolve")


def _when_function(st, line, text, m):
    name = m.group(1)
    if name not in st.surface.functions:
        raise _CompileError(line, f"function '{name}' does not resolve")
    node = _resolve(_whole(m.group(2), line), st.bindings, line)
    tag, val = node
    if tag == "obj":
        params = st.surface.functions[name]
        for key, _ in val:
            if key not in params:
                raise _CompileError(line, f"parameter '{key}' does not resolve")
        args = val
    elif tag == "arr":
        args = [(None, item) for item in val]
    else:
        args = [(None, node)]
    return ("call", name, args)


def _then_finding(st, line, text, m):
    return ("finding", m.group(2), m.group(3))


def _then_equals(st, line, text, m):
    return ("equals", m.group(1), _resolve(_whole(m.group(2), line), st.bindings, line))


_TEMPLATES = {
    "Given": [
        (re.compile(r"a ([A-Za-z_][A-Za-z0-9_]*) is (.+)", re.S), _given_fixture),
        (re.compile(r"a ([A-Z][A-Za-z0-9_]*) with (.+)", re.S), _given_type),
    ],
    "When": [
        (re.compile(r"the client calls ([A-Z]+) (\S+) with (.+)", re.S), _when_endpoint),
        (re.compile(r"([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*) is invoked with (.+)", re.S),
         _when_function),
    ],
    "Then": [
        (re.compile(r"the (.+?) contains a ([A-Za-z]+)-severity finding for rule (\S+)", re.S),
         _then_finding),
        (re.compile(f"({_PATH}) equals (.+)", re.S), _then_equals),
    ],
}


def _bind(criterion, surface):
    st = _Binder(surface)
    ops = []
    for line, text in _steps(criterion.gherkin):
        step = _STEP_RX.fullmatch(text)
        for rx, handler in _TEMPLATES.get(step.group(1), ()):
            m = rx.fullmatch(step.group(2))
            if m:
                ops.append(handler(st, line, text, m))
                break
        else:
            raise _unmatched(line, text)
    return ops


# ---------------------------------------------------------------------------
# Emit (pytest)
# ---------------------------------------------------------------------------

_FINDING_HELPER = [
    "def _cc_get(obj, key):",
    "    return obj.get(key) if isinstance(obj, dict) else getattr(obj, key, None)",
    "",
    "",
    "def _cc_has_finding(result, severity, rule):",
    "    findings = result if isinstance(result, list) else _cc_get(result, \"findings\")",
    "    return any(",
    "        _cc_get(f, \"severity\") == severity and rule in (_cc_get(f, \"rule\"), _cc_get(f, \"rule_id\"))",
    "        for f in findings",
    "    )",
]


def _py(node):
    tag, val = node
    if tag == "obj":
        return "{" + ", ".join(json.dumps(k) + ": " + _py(v) for k, v in val) + "}"
    if tag == "arr":
        return "[" + ", ".join(_py(v) for v in val) + "]"
    if tag == "var":
        return val
    return repr(val) if val is None or isinstance(val, bool) else json.dumps(val)


def _py_args(args):
    return ", ".join(_py(n) if k is None else f"{k}={_py(n)}" for k, n in args)


_EMITTERS = {
    "bind": lambda op, mod: f"{op[1]} = {_py(op[2])}",
    "construct": lambda op, mod: f"{op[1]} = {mod}.{op[2]}({_py_args(op[3])})",
    "call": lambda op, mod: f"result = {mod}.{op[1]}({_py_args(op[2])})",
    "equals": lambda op, mod: f"assert result.{op[1]} == {_py(op[2])}",
    "finding": lambda op, mod: f"assert _cc_has_finding(result, {json.dumps(op[1])}, {json.dumps(op[2])})",
}


def _test_slug(criterion_id):
    return criterion_id.lower().replace("-", "_")


def _emit_pytest(criterion, ops, module_name):
    kinds = {op[0] for op in ops}
    lines = [
        f"# Compiled from {criterion.criterion_id} by criterion-compiler. Do not edit.",
        f"# Covers: {criterion.covers}",
    ]
    if kinds & {"construct", "call"}:
        lines.append(f"import {module_name}")
    if "finding" in kinds:
        lines += ["", "", *_FINDING_HELPER]
    body = ["    " + _EMITTERS[op[0]](op, module_name) for op in ops] or ["    pass"]
    lines += ["", "", f"def test_{_test_slug(criterion.criterion_id)}():", *body]
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Public primitive
# ---------------------------------------------------------------------------

def compile_criterion(criterion: ParsedCriterion, surface: InterfaceSurface | None = None) -> dict:
    surface = surface if surface is not None else InterfaceSurface()
    try:
        ops = _bind(criterion, surface)
    except _CompileError as err:
        return {"status": "error", "message": str(err)}
    return {"status": "compiled", "source": _emit_pytest(criterion, ops, surface.module_name)}


# ---------------------------------------------------------------------------
# Component-level compile
# ---------------------------------------------------------------------------

_COVERS_RX = re.compile(r"^[^A-Za-z\n]*covers[^A-Za-z0-9\n]*([A-Za-z0-9][^\s*`,]*)", re.I | re.M)
_KIND_RX = re.compile(r"^[^A-Za-z\n]*kind[^A-Za-z0-9\n]*([A-Za-z][\w-]*)", re.I | re.M)
_TYPE_HEADING_RX = re.compile(r"^# `([^`]+)`[ \t]*$", re.M)
_JSON_BLOCK_RX = re.compile(r"^```json[ \t]*\n(.*?)^```", re.M | re.S)
_FUNC_RX = re.compile(r"([A-Za-z_][A-Za-z0-9_.]*)\(")


def _rel(path, repo_root):
    p = Path(path).resolve()
    root = Path(repo_root).resolve()
    return (p.relative_to(root) if p.is_relative_to(root) else p).as_posix()


def _first(rx, text):
    m = rx.search(text)
    return m.group(1) if m else ""


def _read_criterion(path, repo_root):
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    start = next((i for i, ln in enumerate(lines) if ln.strip() == "```gherkin"), len(lines))
    end = next((j for j in range(start + 1, len(lines)) if lines[j].strip().startswith("```")), len(lines))
    criterion = ParsedCriterion(
        criterion_id=path.stem,
        covers=_first(_COVERS_RX, text),
        kind=_first(_KIND_RX, text),
        gherkin="\n".join(lines[start + 1:end]),
        file=_rel(path, repo_root),
    )
    return criterion, start + 1


def _params(line, i):
    depth = 0
    parts = [""]
    for c in line[i:]:
        if c in "([{":
            depth += 1
        elif c in ")]}":
            if depth == 0:
                break
            depth -= 1
        elif c == "," and depth == 0:
            parts.append("")
            continue
        parts[-1] += c
    names = (re.split(r"[:=]", p)[0].strip() for p in parts)
    return [n for n in names if n]


def _json_keys(text):
    try:
        obj = json.loads(text)
    except ValueError:
        obj = None
    return list(obj) if isinstance(obj, dict) else []


def _read_surface(iface, slug):
    functions = {}
    lib = iface / "library.md"
    text = lib.read_text(encoding="utf-8") if lib.is_file() else ""
    in_block = plain = False
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("```"):
            plain = not in_block and line == "```"
            in_block = not in_block
            continue
        m = _FUNC_RX.match(line)
        if plain and m:
            functions[m.group(1)] = _params(line, m.end())
    types = {}
    for path in sorted((iface / "data").glob("*.md")):
        data = path.read_text(encoding="utf-8")
        heading = _TYPE_HEADING_RX.search(data)
        if heading:
            block = _JSON_BLOCK_RX.search(data)
            types[heading.group(1)] = _json_keys(block.group(1) if block else "")
    return InterfaceSurface(functions=functions, types=types, module_name=slug.replace("-", "_"))


def _write_if_changed(path, source):
    data = source.encode("utf-8")
    if path.is_file() and path.read_bytes() == data:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def compile(component_id: str, repo_root: Path, target: str = "pytest", out_dir: Path | None = None) -> CompileReport:
    if target != "pytest":
        raise ValueError(f"unsupported --target value '{target}' (only 'pytest' is supported)")
    repo_root = Path(repo_root)
    slug = component_id.removeprefix("comp-")
    comp_dir = repo_root / "specs" / "components" / slug
    if not comp_dir.is_dir():
        raise ValueError(f"unknown component id '{component_id}'")
    out = Path(out_dir) if out_dir is not None else repo_root / "verification" / slug / "compiled"
    surface = _read_surface(comp_dir / "interface", slug)
    outputs = []
    summary = {"compiled": 0, "errors": 0, "skipped_non_compiled_kind": 0}
    for path in sorted((comp_dir / "acceptance").glob("*.md")):
        criterion, offset = _read_criterion(path, repo_root)
        if criterion.kind != "compiled":
            summary["skipped_non_compiled_kind"] += 1
            continue
        result = compile_criterion(criterion, surface)
        entry = {"criterion_id": criterion.criterion_id, "covers": criterion.covers}
        if result["status"] == "compiled":
            test_file = out / f"test_{_test_slug(criterion.criterion_id)}.py"
            _write_if_changed(test_file, result["source"])
            entry.update(status="compiled", file=_rel(test_file, repo_root))
            summary["compiled"] += 1
        else:
            number, rest = result["message"][len("line "):].split(": ", 1)
            entry.update(status="error", file=criterion.file,
                         message=f"line {int(number) + offset}: {rest}")
            summary["errors"] += 1
        outputs.append(entry)
    return CompileReport(outputs=outputs, gate_version=GATE_VERSION, summary=summary)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _git_root():
    return subprocess.run(["git", "rev-parse", "--show-toplevel"],
                          capture_output=True, text=True).stdout.strip()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="hotdocs compile-criteria")
    parser.add_argument("component_id")
    parser.add_argument("--target", default="pytest")
    parser.add_argument("--out")
    parser.add_argument("--repo-root")
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return exc.code
    repo_root = Path(args.repo_root or _git_root())
    try:
        report = compile(args.component_id, repo_root, args.target,
                         Path(args.out) if args.out else None)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(asdict(report), indent=2))
    return 1 if report.summary["errors"] else 0
