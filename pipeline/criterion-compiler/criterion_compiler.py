"""Criterion compiler: deterministic compilation of `kind: compiled`
Given/When/Then acceptance criteria into pytest test code.

No model, agent or network access is involved at any stage: the work is
grammar parsing, interface binding, and deterministic code emission,
structured as two phases (parse+bind, then emit) per R-COMPILE-011.
"""

import argparse
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

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
    pass


class _Var:
    """A reference to a value constructed by a `Given a <Type> with ...` step."""

    def __init__(self, name):
        self.name = name


# ---------------------------------------------------------------------------
# Grammar
# ---------------------------------------------------------------------------

_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_ACCESS = re.compile(
    r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*|\[[^\[\]]*\])+"
)
_KEYWORD = re.compile(r"(Given|When|Then) ")
_TYPE_STEP = re.compile(r"a ([A-Z][A-Za-z0-9_]*) with\s+(.+)")
_FIXTURE_STEP = re.compile(r"a ([A-Za-z_][A-Za-z0-9_]*) is\s+(.+)")
_INVOKE_STEP = re.compile(
    r"([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*) is invoked with\s+(.+)"
)
_CLIENT_STEP = re.compile(r"the client calls ([A-Z]+) (\S+) with\s+(.+)")
_FINDING_STEP = re.compile(
    r"the (.+?) contains a ([A-Za-z]+)-severity finding for rule (\S+)"
)
_EQUALS_STEP = re.compile(
    r"([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*|\[-?\d+\])*) equals\s+(.+)"
)
_FIELD = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)\s*:")
_CONSTANTS = {"true": True, "false": False, "null": None}
_DECODER = json.JSONDecoder()

_KIND_RE = re.compile(
    r"^[ \t>*_|\-]*`?Kind`?[*_` \t]*[:|][*_` \t|]*([A-Za-z0-9][\w.\-]*)",
    re.MULTILINE | re.IGNORECASE,
)
_COVERS_RE = re.compile(
    r"^[ \t>*_|\-]*`?Covers`?[*_` \t]*[:|][*_` \t|]*([A-Za-z0-9][\w.\-]*)",
    re.MULTILINE | re.IGNORECASE,
)


def _slot_end(text, start, stop):
    """End index of the value slot beginning at `start` (for error quoting)."""
    depth = 0
    i = start
    n = len(text)
    while i < n:
        ch = text[i]
        if ch == '"':
            i += 1
            while i < n and text[i] != '"':
                i += 2 if text[i] == "\\" else 1
        elif ch in "([{":
            depth += 1
        elif ch in ")]}":
            if depth == 0:
                return i
            depth -= 1
        elif depth == 0 and ch in stop:
            return i
        i += 1
    return n


class _Literal:
    """Parses JSON-like literal data; a bare identifier in a leaf position is
    substituted, at compile time, by the value an earlier `Given` bound."""

    def __init__(self, text, line, bindings):
        self.text = text
        self.line = line
        self.bindings = bindings
        self.pos = 0

    def _ws(self):
        while self.pos < len(self.text) and self.text[self.pos].isspace():
            self.pos += 1

    def _peek(self):
        return self.text[self.pos:self.pos + 1]

    def _malformed(self):
        raise _CompileError(
            f"line {self.line}: '{self.text.strip()}' is not a literal"
        )

    def _expression(self, start, stop):
        expr = self.text[start:_slot_end(self.text, start, stop)].strip()
        detail = ": field/index access" if _ACCESS.fullmatch(expr) else ""
        raise _CompileError(f"line {self.line}: '{expr}' is not a literal{detail}")

    def value(self, stop):
        self._ws()
        start = self.pos
        if start >= len(self.text) or self.text[start] in stop:
            self._malformed()
        ch = self.text[start]
        name = None
        node = None
        if ch == "{":
            node = self._object()
        elif ch == "[":
            node = self._array()
        elif ch == '"' or ch == "-" or ch.isdigit():
            try:
                node, self.pos = _DECODER.raw_decode(self.text, start)
            except ValueError:
                self._expression(start, stop)
        else:
            match = _IDENT.match(self.text, start)
            if match is None:
                self._expression(start, stop)
            name = match.group()
            self.pos = match.end()
        self._ws()
        if self.pos < len(self.text) and self.text[self.pos] not in stop:
            self._expression(start, stop)
        if name is None:
            return node
        if name in _CONSTANTS:
            return _CONSTANTS[name]
        if name not in self.bindings:
            raise _CompileError(f"line {self.line}: unresolved reference '{name}'")
        return self.bindings[name]

    def _object(self):
        self.pos += 1
        result = {}
        self._ws()
        if self._peek() == "}":
            self.pos += 1
            return result
        while True:
            self._ws()
            if self._peek() != '"':
                self._malformed()
            try:
                key, self.pos = _DECODER.raw_decode(self.text, self.pos)
            except ValueError:
                self._malformed()
            self._ws()
            if self._peek() != ":":
                self._malformed()
            self.pos += 1
            result[key] = self.value(",}")
            if self._peek() == ",":
                self.pos += 1
                continue
            if self._peek() == "}":
                self.pos += 1
                return result
            self._malformed()

    def _array(self):
        self.pos += 1
        items = []
        self._ws()
        if self._peek() == "]":
            self.pos += 1
            return items
        while True:
            items.append(self.value(",]"))
            if self._peek() == ",":
                self.pos += 1
                continue
            if self._peek() == "]":
                self.pos += 1
                return items
            self._malformed()


def _snake(name):
    s = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", name)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s).lower()


# ---------------------------------------------------------------------------
# Phase 1: parse + bind (target-independent)
# ---------------------------------------------------------------------------


def _split_steps(gherkin):
    steps = []
    current = None
    for number, raw in enumerate(gherkin.splitlines(), 1):
        stripped = raw.strip()
        if not stripped:
            current = None
            continue
        match = _KEYWORD.match(raw.lstrip())
        if match:
            current = [number, match.group(1), raw.lstrip()[match.end():].strip()]
            steps.append(current)
        elif current is None:
            current = [number, None, stripped]
            steps.append(current)
        else:
            current[2] += " " + stripped
    return steps


def _unresolved(line, what, name):
    raise _CompileError(f"line {line}: {what} '{name}' does not resolve")


def _bind_construct(line, text, match, surface, bindings):
    type_name, fields_text = match.groups()
    if surface is None or type_name not in surface.types:
        _unresolved(line, "type", type_name)
    declared = surface.types[type_name]
    parser = _Literal(fields_text, line, bindings)
    fields = []
    while True:
        parser._ws()
        field_match = _FIELD.match(fields_text, parser.pos)
        if field_match is None:
            raise _CompileError(
                f"line {line}: step 'Given {text}' does not match any recognized template"
            )
        name = field_match.group(1)
        if name not in declared:
            raise _CompileError(
                f"line {line}: field '{name}' of type '{type_name}' does not resolve"
            )
        parser.pos = field_match.end()
        fields.append((name, parser.value(",")))
        if parser.pos >= len(fields_text):
            break
        parser.pos += 1
    var = _snake(type_name)
    bindings[var] = _Var(var)
    return ("construct", var, type_name, fields)


def _bind_step(line, keyword, text, surface, bindings):
    if keyword == "Given":
        match = _TYPE_STEP.fullmatch(text)
        if match:
            return _bind_construct(line, text, match, surface, bindings)
        match = _FIXTURE_STEP.fullmatch(text)
        if match:
            node = _Literal(match.group(2), line, bindings).value("")
            bindings[match.group(1)] = node
            return ("fixture", match.group(1), node)
    elif keyword == "When":
        match = _INVOKE_STEP.fullmatch(text)
        if match:
            name, args_text = match.groups()
            if surface is None or name not in surface.functions:
                _unresolved(line, "function", name)
            node = _Literal(args_text, line, bindings).value("")
            form = {"{": "kwargs", "[": "positional"}.get(args_text[0], "single")
            return ("invoke", name, form, node)
        match = _CLIENT_STEP.fullmatch(text)
        if match:
            _unresolved(line, "endpoint", f"{match.group(1)} {match.group(2)}")
    elif keyword == "Then":
        match = _FINDING_STEP.fullmatch(text)
        if match:
            return ("finding", match.group(2), match.group(3))
        match = _EQUALS_STEP.fullmatch(text)
        if match:
            node = _Literal(match.group(2), line, bindings).value("")
            return ("equals", match.group(1), node)
    written = f"{keyword} {text}" if keyword else text
    raise _CompileError(
        f"line {line}: step '{written}' does not match any recognized template"
    )


def _parse_and_bind(criterion, surface):
    bindings = {}
    return [
        _bind_step(line, keyword, text, surface, bindings)
        for line, keyword, text in _split_steps(criterion.gherkin)
    ]


# ---------------------------------------------------------------------------
# Phase 2: emit (one emitter per --target)
# ---------------------------------------------------------------------------

_FIELD_HELPER = '''def _field(obj, *names):
    for name in names:
        if isinstance(obj, dict) and name in obj:
            return obj[name]
        if not isinstance(obj, dict) and hasattr(obj, name):
            return getattr(obj, name)
    return None'''


def _render(node):
    if isinstance(node, bool):
        return "True" if node else "False"
    if node is None:
        return "None"
    if isinstance(node, _Var):
        return node.name
    if isinstance(node, dict):
        return "{" + ", ".join(
            f"{json.dumps(k)}: {_render(v)}" for k, v in node.items()
        ) + "}"
    if isinstance(node, list):
        return "[" + ", ".join(_render(v) for v in node) + "]"
    return json.dumps(node)


def _render_args(form, node):
    if form == "kwargs":
        return ", ".join(f"{k}={_render(v)}" for k, v in node.items())
    if form == "positional":
        return ", ".join(_render(v) for v in node)
    return _render(node)


def _test_name(criterion_id):
    return "test_" + criterion_id.lower().replace("-", "_")


def _emit_pytest(criterion, steps, module_name):
    prefix = f"{module_name}." if module_name else ""
    body = []
    needs_module = False
    needs_helper = False
    for step in steps:
        tag = step[0]
        if tag == "fixture":
            body.append(f"{step[1]} = {_render(step[2])}")
        elif tag == "construct":
            _, var, type_name, fields = step
            args = ", ".join(f"{name}={_render(value)}" for name, value in fields)
            body.append(f"{var} = {prefix}{type_name}({args})")
            needs_module = True
        elif tag == "invoke":
            _, name, form, node = step
            body.append(f"result = {prefix}{name}({_render_args(form, node)})")
            needs_module = True
        elif tag == "equals":
            body.append(f"assert result.{step[1]} == {_render(step[2])}")
        else:
            _, severity, rule = step
            body.append(
                "assert any(_field(finding, \"severity\") == "
                f"{json.dumps(severity)} and _field(finding, \"rule_id\", \"rule\") == "
                f"{json.dumps(rule)} for finding in (result if isinstance(result, list) "
                "else _field(result, \"findings\")))"
            )
            needs_helper = True
    lines = [f"# Covers: {criterion.covers}"]
    if needs_module and module_name:
        lines.append(f"import {module_name}")
    if needs_helper:
        lines += ["", "", _FIELD_HELPER]
    lines += ["", "", f"def {_test_name(criterion.criterion_id)}():"]
    lines += ["    " + line for line in (body or ["pass"])]
    return "\n".join(lines) + "\n"


_EMITTERS = {"pytest": _emit_pytest}


# ---------------------------------------------------------------------------
# Public primitive
# ---------------------------------------------------------------------------


def compile_criterion(criterion: ParsedCriterion, surface: Optional[InterfaceSurface] = None) -> dict:
    try:
        steps = _parse_and_bind(criterion, surface)
    except _CompileError as exc:
        return {"status": "error", "message": str(exc)}
    module_name = surface.module_name if surface is not None else ""
    return {"status": "compiled", "source": _EMITTERS["pytest"](criterion, steps, module_name)}


# ---------------------------------------------------------------------------
# Corpus reading
# ---------------------------------------------------------------------------


def _slug(component_id):
    return component_id[len("comp-"):] if component_id.startswith("comp-") else component_id


def _fenced_block(lines, opener):
    for index, line in enumerate(lines):
        if line.strip() == opener:
            body = []
            for inner in lines[index + 1:]:
                if inner.strip().startswith("```"):
                    break
                body.append(inner)
            return index + 1, body
    return 0, []


def _split_top(text):
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
    return parts


def _signature(line):
    match = re.match(r"([A-Za-z_][A-Za-z0-9_.]*)\(", line)
    if match is None:
        return None
    depth = 0
    end = len(line)
    for index in range(match.end() - 1, len(line)):
        ch = line[index]
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
            if depth == 0:
                end = index
                break
    names = [re.split(r"[:=]", part, 1)[0].strip() for part in _split_top(line[match.end():end])]
    return match.group(1), [name for name in names if name]


def _read_surface(interface_dir, module_name):
    functions = {}
    library = interface_dir / "library.md"
    if library.is_file():
        in_fence = False
        plain = False
        for line in library.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith("```"):
                plain = not in_fence and stripped == "```"
                in_fence = not in_fence
                continue
            if plain:
                parsed = _signature(line)
                if parsed:
                    functions[parsed[0]] = parsed[1]
    types = {}
    for path in sorted((interface_dir / "data").glob("*.md")):
        lines = path.read_text(encoding="utf-8").splitlines()
        heading = next((line for line in lines if line.startswith("# ")), "")
        match = re.fullmatch(r"# `([A-Za-z_][A-Za-z0-9_]*)`\s*", heading)
        if match:
            try:
                example = json.loads("\n".join(_fenced_block(lines, "```json")[1]))
            except ValueError:
                example = None
            types[match.group(1)] = list(example) if isinstance(example, dict) else []
    return InterfaceSurface(functions=functions, types=types, module_name=module_name)


def _display(path, repo_root):
    full = Path(path).resolve()
    try:
        return full.relative_to(Path(repo_root).resolve()).as_posix()
    except ValueError:
        return str(full)


def _first(regex, text):
    match = regex.search(text)
    return match.group(1) if match else ""


def compile(component_id: str, repo_root: Path, target: str = "pytest", out_dir: Optional[Path] = None) -> CompileReport:
    if target not in _EMITTERS:
        raise ValueError(f"unsupported --target value '{target}' (supported: pytest)")
    repo_root = Path(repo_root)
    slug = _slug(component_id)
    component_dir = repo_root / "specs" / "components" / slug
    surface = _read_surface(component_dir / "interface", slug.replace("-", "_"))
    out = Path(out_dir) if out_dir is not None else repo_root / "verification" / slug / "compiled"
    outputs = []
    summary = {"compiled": 0, "errors": 0, "skipped_non_compiled_kind": 0}
    for path in sorted((component_dir / "acceptance").glob("*.md")):
        text = path.read_text(encoding="utf-8")
        kind = _first(_KIND_RE, text)
        if kind != "compiled":
            summary["skipped_non_compiled_kind"] += 1
            continue
        offset, body = _fenced_block(text.splitlines(), "```gherkin")
        criterion = ParsedCriterion(
            criterion_id=path.stem,
            covers=_first(_COVERS_RE, text),
            kind=kind,
            gherkin="\n".join(body),
            file=_display(path, repo_root),
        )
        result = compile_criterion(criterion, surface)
        entry = {"criterion_id": criterion.criterion_id, "covers": criterion.covers}
        if result["status"] == "compiled":
            target_file = out / (_test_name(criterion.criterion_id) + ".py")
            data = result["source"].encode("utf-8")
            if not target_file.exists() or target_file.read_bytes() != data:
                target_file.parent.mkdir(parents=True, exist_ok=True)
                target_file.write_bytes(data)
            entry.update(status="compiled", file=_display(target_file, repo_root))
            summary["compiled"] += 1
        else:
            message = re.sub(
                r"^line (\d+): ",
                lambda m: f"line {int(m.group(1)) + offset}: ",
                result["message"],
                count=1,
            )
            entry.update(status="error", file=criterion.file, message=message)
            summary["errors"] += 1
        outputs.append(entry)
    return CompileReport(outputs=outputs, gate_version=GATE_VERSION, summary=summary)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _git_root():
    completed = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=True,
    )
    return Path(completed.stdout.strip())


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(prog="hotdocs compile-criteria")
    parser.add_argument("component_id")
    parser.add_argument("--target", default="pytest")
    parser.add_argument("--out")
    parser.add_argument("--repo-root")
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return exc.code
    if args.target not in _EMITTERS:
        print(
            f"error: unsupported --target value '{args.target}' (supported: pytest)",
            file=sys.stderr,
        )
        return 2
    repo_root = Path(args.repo_root) if args.repo_root else _git_root()
    if not (repo_root / "specs" / "components" / _slug(args.component_id)).is_dir():
        print(f"error: unknown component id '{args.component_id}'", file=sys.stderr)
        return 2
    report = compile(
        args.component_id,
        repo_root,
        args.target,
        Path(args.out) if args.out else None,
    )
    print(json.dumps(asdict(report), indent=2))
    return 1 if report.summary["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())