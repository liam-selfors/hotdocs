"""criterion-compiler -- sealed, permanently hand-authored.

Deterministically compiles `kind: compiled` Given/When/Then acceptance
criteria into executable pytest scaffolding, with no model involved at
any step (R-COMPILE-008). See specs/components/criterion-compiler/ for
the full spec; specs/architecture/step-phrase-grammar.md for the fixed
step vocabulary this implements.

Never agent-generated (component.md: sealed: true) -- the trust anchor
for `compiled`-kind criteria only holds if the compiler itself is not
agent-generated. See verification/criterion-compiler/BOOTSTRAP.md for
every underspecified design choice this file had to resolve on its own.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

GATE_VERSION = "criterion-compiler@1.0.0"
SUPPORTED_TARGETS = {"pytest"}


class CompileError(Exception):
    """A specific, located compile error -- never a silent skip or a
    best-effort guess (R-COMPILE-001/002/007)."""

    def __init__(self, message: str, file: str = "", line: int = 0):
        super().__init__(message)
        self.message = message
        self.file = file
        self.line = line


@dataclass
class CompileReport:
    outputs: list[dict]
    gate_version: str
    summary: dict

    def to_dict(self) -> dict:
        return {"outputs": self.outputs, "gate_version": self.gate_version, "summary": self.summary}


# ---------------------------------------------------------------------------
# acceptance/*.md parsing -- Covers:, Kind:, and the gherkin block.
# ---------------------------------------------------------------------------

_COVERS_RE = re.compile(r"^Covers:\s*(\S+)", re.MULTILINE)
_KIND_RE = re.compile(r"^Kind:\s*(\S+)", re.MULTILINE)
_GHERKIN_RE = re.compile(r"```gherkin\n(.*?)\n```", re.DOTALL)


@dataclass
class ParsedCriterion:
    criterion_id: str
    covers: str
    kind: str
    gherkin: str
    file: str


def _parse_criterion_file(path: Path) -> ParsedCriterion:
    text = path.read_text(encoding="utf-8")
    covers_m = _COVERS_RE.search(text)
    kind_m = _KIND_RE.search(text)
    gherkin_m = _GHERKIN_RE.search(text)
    return ParsedCriterion(
        criterion_id=path.stem,
        covers=covers_m.group(1) if covers_m else "",
        kind=kind_m.group(1) if kind_m else "",
        gherkin=gherkin_m.group(1) if gherkin_m else "",
        file=path.name,
    )


# ---------------------------------------------------------------------------
# Gherkin -> scenarios -> steps.
#
# A `compiled` criterion's gherkin block holds one or more scenarios,
# each a contiguous run of one-or-more Given lines, exactly one When
# line, and one-or-more Then lines -- scenarios separated by a blank
# line (BOOTSTRAP.md "Scenario grouping"). A step's text may wrap
# across physical lines (indentation continuation); a continuation
# line is any non-blank line not itself starting a new Given/When/Then.
# ---------------------------------------------------------------------------

_STEP_KEYWORD_RE = re.compile(r"^(Given|When|Then)\s+(.*)$")


@dataclass
class Step:
    keyword: str  # "Given" | "When" | "Then"
    text: str
    line: int


@dataclass
class Scenario:
    steps: list[Step]


def _split_scenarios(gherkin: str, start_line: int) -> list[Scenario]:
    lines = gherkin.split("\n")
    raw_steps: list[Step] = []
    current: Step | None = None
    for offset, raw_line in enumerate(lines):
        lineno = start_line + offset
        stripped = raw_line.strip()
        m = _STEP_KEYWORD_RE.match(stripped)
        if m:
            if current is not None:
                raw_steps.append(current)
            current = Step(keyword=m.group(1), text=m.group(2), line=lineno)
        elif not stripped:
            if current is not None:
                raw_steps.append(current)
                current = None
        elif current is not None:
            current.text += " " + stripped
    if current is not None:
        raw_steps.append(current)

    scenarios: list[Scenario] = []
    bucket: list[Step] = []
    for step in raw_steps:
        if step.keyword == "Given" and bucket and bucket[-1].keyword in ("Then",):
            scenarios.append(Scenario(steps=bucket))
            bucket = []
        bucket.append(step)
    if bucket:
        scenarios.append(Scenario(steps=bucket))
    return scenarios


# ---------------------------------------------------------------------------
# interface/ resolution (R-COMPILE-002).
#
# library.md's fenced code block: one function signature per
# non-blank line, `name(params) -> ReturnType`. interface/data/<Type>.md:
# the `# `Type`` heading names a Type; its JSON example's top-level keys
# are its fields (BOOTSTRAP.md "Interface resolution").
# ---------------------------------------------------------------------------

_FUNC_SIG_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_.]*)\s*\(([^)]*)\)")
_TYPE_HEADING_RE = re.compile(r"^#\s*`([A-Za-z_][A-Za-z0-9_]*)`")
_JSON_BLOCK_RE = re.compile(r"```json\n(.*?)\n```", re.DOTALL)


@dataclass
class InterfaceSurface:
    functions: dict[str, list[str]] = field(default_factory=dict)  # name -> param names
    types: dict[str, list[str]] = field(default_factory=dict)  # Type -> field names


def _load_interface_surface(repo_root: Path, component_slug: str) -> InterfaceSurface:
    surface = InterfaceSurface()
    iface_dir = repo_root / "specs" / "components" / component_slug / "interface"
    library_md = iface_dir / "library.md"
    if library_md.is_file():
        for block in re.findall(r"```\n(.*?)\n```", library_md.read_text(encoding="utf-8"), re.DOTALL):
            for line in block.splitlines():
                m = _FUNC_SIG_RE.match(line.strip())
                if m:
                    name = m.group(1)
                    params_raw = m.group(2)
                    params = []
                    for part in params_raw.split(","):
                        part = part.strip().lstrip("*")
                        if not part or part == "":
                            continue
                        pname = part.split(":")[0].split("=")[0].strip()
                        if pname:
                            params.append(pname)
                    surface.functions[name] = params

    data_dir = iface_dir / "data"
    if data_dir.is_dir():
        for data_file in data_dir.glob("*.md"):
            text = data_file.read_text(encoding="utf-8")
            type_m = _TYPE_HEADING_RE.search(text)
            if not type_m:
                continue
            type_name = type_m.group(1)
            json_m = _JSON_BLOCK_RE.search(text)
            fields: list[str] = []
            if json_m:
                try:
                    example = json.loads(json_m.group(1))
                    if isinstance(example, dict):
                        fields = list(example.keys())
                except json.JSONDecodeError:
                    fields = []
            surface.types[type_name] = fields
    return surface


# ---------------------------------------------------------------------------
# Literal / identifier parsing (R-COMPILE-007/012).
#
# A literal is a JSON scalar/string/object/array, or a bare identifier
# in a leaf position (resolved at compile time against earlier-bound
# fixtures, R-COMPILE-007). Anything else left over after parsing the
# longest valid literal/identifier prefix -- an operator, field/index
# access, concatenation, a call -- is an expression and a compile error.
# ---------------------------------------------------------------------------

_IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_WS_RE = re.compile(r"\s*")


class _LiteralParser:
    def __init__(self, text: str, bound: set[str], file: str, line: int):
        self.text = text
        self.pos = 0
        self.bound = bound
        self.file = file
        self.line = line

    def _skip_ws(self) -> None:
        m = _WS_RE.match(self.text, self.pos)
        if m:
            self.pos = m.end()

    def parse_value(self) -> Any:
        self._skip_ws()
        if self.pos >= len(self.text):
            raise CompileError("expected a literal value, found nothing", self.file, self.line)
        ch = self.text[self.pos]
        if ch == '"':
            return self._parse_string()
        if ch == "{":
            return self._parse_object()
        if ch == "[":
            return self._parse_array()
        if ch == "-" or ch.isdigit():
            return self._parse_number()
        if self.text[self.pos:self.pos + 4] == "true":
            self.pos += 4
            return True
        if self.text[self.pos:self.pos + 5] == "false":
            self.pos += 5
            return False
        if self.text[self.pos:self.pos + 4] == "null":
            self.pos += 4
            return None
        m = _IDENT_RE.match(self.text, self.pos)
        if m:
            name = m.group(0)
            self.pos = m.end()
            if name not in self.bound:
                raise CompileError(
                    f"unresolved reference '{name}' -- not bound by any earlier Given step in this criterion",
                    self.file, self.line,
                )
            return _FixtureRef(name)
        raise CompileError(f"text does not start with a recognized literal: {self.text[self.pos:]!r}", self.file, self.line)

    def _parse_string(self) -> str:
        start = self.pos
        self.pos += 1
        out = []
        while self.pos < len(self.text):
            ch = self.text[self.pos]
            if ch == "\\" and self.pos + 1 < len(self.text):
                out.append(self.text[self.pos + 1])
                self.pos += 2
                continue
            if ch == '"':
                self.pos += 1
                return "".join(out)
            out.append(ch)
            self.pos += 1
        raise CompileError("unterminated string literal", self.file, self.line)

    def _parse_number(self) -> Any:
        m = re.match(r"-?\d+(\.\d+)?", self.text[self.pos:])
        if not m:
            raise CompileError("invalid number literal", self.file, self.line)
        raw = m.group(0)
        self.pos += len(raw)
        return float(raw) if "." in raw else int(raw)

    def _parse_object(self) -> dict:
        self.pos += 1  # {
        obj: dict[str, Any] = {}
        self._skip_ws()
        if self.pos < len(self.text) and self.text[self.pos] == "}":
            self.pos += 1
            return obj
        while True:
            self._skip_ws()
            if self.pos >= len(self.text) or self.text[self.pos] != '"':
                raise CompileError("expected a quoted object key", self.file, self.line)
            key = self._parse_string()
            self._skip_ws()
            if self.pos >= len(self.text) or self.text[self.pos] != ":":
                raise CompileError("expected ':' after object key", self.file, self.line)
            self.pos += 1
            self._skip_ws()
            obj[key] = self.parse_value()
            self._skip_ws()
            if self.pos < len(self.text) and self.text[self.pos] == ",":
                self.pos += 1
                continue
            if self.pos < len(self.text) and self.text[self.pos] == "}":
                self.pos += 1
                return obj
            raise CompileError("expected ',' or '}' in object literal", self.file, self.line)

    def _parse_array(self) -> list:
        self.pos += 1  # [
        arr: list[Any] = []
        self._skip_ws()
        if self.pos < len(self.text) and self.text[self.pos] == "]":
            self.pos += 1
            return arr
        while True:
            self._skip_ws()
            arr.append(self.parse_value())
            self._skip_ws()
            if self.pos < len(self.text) and self.text[self.pos] == ",":
                self.pos += 1
                continue
            if self.pos < len(self.text) and self.text[self.pos] == "]":
                self.pos += 1
                return arr
            raise CompileError("expected ',' or ']' in array literal", self.file, self.line)

    def parse_whole(self) -> Any:
        """Parses one literal/identifier value and requires it to consume
        the entire (trimmed) input -- any leftover text is an expression
        (operator, field/index access, concatenation, call), never a
        silently-ignored suffix."""
        value = self.parse_value()
        self._skip_ws()
        if self.pos < len(self.text):
            leftover = self.text[self.pos:]
            if leftover.startswith("."):
                raise CompileError(
                    f"field/index access ({leftover!r}) is not a literal -- "
                    "bind the needed field directly in its own Given step instead",
                    self.file, self.line,
                )
            raise CompileError(
                f"{self.text.strip()!r} is not a literal (expression evaluation is not permitted)",
                self.file, self.line,
            )
        return value


@dataclass(frozen=True)
class _FixtureRef:
    name: str


@dataclass(frozen=True)
class _RawSource:
    """Already-rendered Python source (a type constructor call), spliced
    verbatim rather than re-rendered as a JSON literal."""

    text: str


def _parse_literal(text: str, bound: set[str], file: str, line: int) -> Any:
    return _LiteralParser(text.strip(), bound, file, line).parse_whole()


def _literal_to_py(value: Any, resolve: dict[str, Any] | None = None) -> str:
    """Renders a parsed literal (which may contain nested _FixtureRef
    leaves) as Python source text. A fixture reference is inlined as
    its own already-known literal value -- a real compile-time
    substitution, never a variable name left for Python's own runtime
    lookup to resolve (AC-COMPILE-012: "no runtime lookup ... in the
    generated code")."""
    resolve = resolve or {}
    if isinstance(value, _FixtureRef):
        return _literal_to_py(resolve[value.name], resolve)
    if isinstance(value, _RawSource):
        return value.text
    if isinstance(value, dict):
        return "{" + ", ".join(f"{json.dumps(k)}: {_literal_to_py(v, resolve)}" for k, v in value.items()) + "}"
    if isinstance(value, list):
        return "[" + ", ".join(_literal_to_py(v, resolve) for v in value) + "]"
    return json.dumps(value)


# ---------------------------------------------------------------------------
# Step matching against the fixed grammar (R-COMPILE-001).
# ---------------------------------------------------------------------------

_GIVEN_SIMPLE_RE = re.compile(r"^a\s+([A-Za-z_][A-Za-z0-9_]*)\s+is\s+(.+)$")
_GIVEN_TYPE_RE = re.compile(r"^a\s+([A-Z][A-Za-z0-9_]*)\s+with\s+(.+)$")
_WHEN_INVOKE_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_.]*)\s+is\s+invoked\s+with\s+(.+)$")
_WHEN_HTTP_RE = re.compile(r"^the\s+client\s+calls\s+(\w+)\s+(\S+)\s+with\s+(.+)$")
_THEN_EQUALS_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_.\[\]]*)\s+equals\s+(.+)$")
_THEN_FINDING_RE = re.compile(
    r"^the\s+(\w+)\s+contains\s+a\s+(\w+)-severity\s+finding\s+for\s+rule\s+([\w\-]+)$"
)


def _snake(name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


class _ScenarioCompiler:
    def __init__(self, surface: InterfaceSurface, file: str):
        self.surface = surface
        self.file = file
        self.bound_values: dict[str, Any] = {}  # fixture name -> resolved literal value (or _RawSource)
        self.bound_names: set[str] = set()
        self.setup_lines: list[str] = []
        self.exercise_line: str | None = None
        self.assert_lines: list[str] = []
        self._type_counts: dict[str, int] = {}

    def _bind(self, hint: str) -> str:
        count = self._type_counts.get(hint, 0) + 1
        self._type_counts[hint] = count
        return hint if count == 1 else f"{hint}_{count}"

    def compile_step(self, step: Step) -> None:
        text = step.text.strip()
        if step.keyword == "Given":
            self._compile_given(text, step.line)
        elif step.keyword == "When":
            self._compile_when(text, step.line)
        elif step.keyword == "Then":
            self._compile_then(text, step.line)

    def _compile_given(self, text: str, line: int) -> None:
        m = _GIVEN_SIMPLE_RE.match(text)
        if m:
            fixture_name, literal_text = m.group(1), m.group(2)
            value = _parse_literal(literal_text, self.bound_names, self.file, line)
            self.bound_names.add(fixture_name)
            self.bound_values[fixture_name] = value
            self.setup_lines.append(f"{fixture_name} = {_literal_to_py(value, self.bound_values)}")
            return

        m = _GIVEN_TYPE_RE.match(text)
        if m:
            type_name, fields_text = m.group(1), m.group(2)
            if type_name not in self.surface.types:
                raise CompileError(
                    f"'{type_name}' does not resolve to any declared type in this component's interface/",
                    self.file, line,
                )
            declared_fields = set(self.surface.types[type_name])
            kwargs: dict[str, Any] = {}
            for part in _split_top_level_commas(fields_text):
                field_name, _, literal_text = part.partition(":")
                field_name = field_name.strip()
                if declared_fields and field_name not in declared_fields:
                    raise CompileError(
                        f"'{field_name}' does not resolve to any declared field of '{type_name}'",
                        self.file, line,
                    )
                kwargs[field_name] = _parse_literal(literal_text, self.bound_names, self.file, line)
            fixture_name = self._bind(_snake(type_name))
            kwargs_src = ", ".join(f"{k}={_literal_to_py(v, self.bound_values)}" for k, v in kwargs.items())
            self.bound_names.add(fixture_name)
            self.bound_values[fixture_name] = _RawSource(f"{type_name}({kwargs_src})")
            self.setup_lines.append(f"{fixture_name} = {type_name}({kwargs_src})")
            return

        raise CompileError(
            f"step 'Given {text}' does not match any recognized template in the step grammar",
            self.file, line,
        )

    def _compile_when(self, text: str, line: int) -> None:
        m = _WHEN_INVOKE_RE.match(text)
        if m:
            func_name, args_text = m.group(1), m.group(2)
            if func_name not in self.surface.functions:
                raise CompileError(
                    f"'{func_name}' does not resolve to any declared function in this component's interface/",
                    self.file, line,
                )
            args_value = _parse_literal(args_text, self.bound_names, self.file, line)
            if isinstance(args_value, dict):
                call_args = ", ".join(f"{k}={_literal_to_py(v, self.bound_values)}" for k, v in args_value.items())
            elif isinstance(args_value, list):
                call_args = ", ".join(_literal_to_py(v, self.bound_values) for v in args_value)
            else:
                call_args = _literal_to_py(args_value, self.bound_values)
            self.exercise_line = f"result = {func_name}({call_args})"
            return

        m = _WHEN_HTTP_RE.match(text)
        if m:
            method, path, args_text = m.group(1), m.group(2), m.group(3)
            endpoint_name = f"{method.upper()} {path}"
            if endpoint_name not in self.surface.functions:
                raise CompileError(
                    f"'{endpoint_name}' does not resolve to any declared endpoint in this component's interface/",
                    self.file, line,
                )
            args_value = _parse_literal(args_text, self.bound_names, self.file, line)
            self.exercise_line = (
                f"result = client.{method.lower()}({_literal_to_py(path, self.bound_values)}, "
                f"{_literal_to_py(args_value, self.bound_values)})"
            )
            return

        raise CompileError(
            f"step 'When {text}' does not match any recognized template in the step grammar",
            self.file, line,
        )

    def _compile_then(self, text: str, line: int) -> None:
        m = _THEN_EQUALS_RE.match(text)
        if m:
            result_path, literal_text = m.group(1), m.group(2)
            value = _parse_literal(literal_text, self.bound_names, self.file, line)
            self.assert_lines.append(f"assert result.{result_path} == {_literal_to_py(value, self.bound_values)}")
            return

        m = _THEN_FINDING_RE.match(text)
        if m:
            artifact, severity, rule_id = m.group(1), m.group(2), m.group(3)
            self.assert_lines.append(
                f"assert any(f.rule_id == {rule_id!r} and f.severity == {severity!r} "
                f"for f in {artifact}.findings)"
            )
            return

        raise CompileError(
            f"step 'Then {text}' does not match any recognized template in the step grammar",
            self.file, line,
        )


def _split_top_level_commas(text: str) -> list[str]:
    """Splits a 'field: literal, field: literal' list on commas that are
    not nested inside a {}/[]/"" literal."""
    parts: list[str] = []
    depth = 0
    in_string = False
    current = []
    i = 0
    while i < len(text):
        ch = text[i]
        if in_string:
            current.append(ch)
            if ch == "\\" and i + 1 < len(text):
                current.append(text[i + 1])
                i += 2
                continue
            if ch == '"':
                in_string = False
            i += 1
            continue
        if ch == '"':
            in_string = True
            current.append(ch)
        elif ch in "{[":
            depth += 1
            current.append(ch)
        elif ch in "}]":
            depth -= 1
            current.append(ch)
        elif ch == "," and depth == 0:
            parts.append("".join(current))
            current = []
        else:
            current.append(ch)
        i += 1
    if current:
        parts.append("".join(current))
    return [p for p in parts if p.strip()]


# ---------------------------------------------------------------------------
# pytest emission (R-COMPILE-011 -- emit phase, target-specific).
# ---------------------------------------------------------------------------

def _emit_pytest(criterion: ParsedCriterion, scenarios: list[Scenario], surface: InterfaceSurface) -> str:
    lines = [
        "# Generated by criterion-compiler -- do not edit by hand.",
        f"# Covers: {criterion.covers}",
        "",
    ]
    for idx, scenario in enumerate(scenarios, start=1):
        compiler = _ScenarioCompiler(surface, criterion.file)
        for step in scenario.steps:
            compiler.compile_step(step)
        suffix = "" if len(scenarios) == 1 else f"_scenario_{idx}"
        func_name = f"test_{criterion.criterion_id.lower().replace('-', '_')}{suffix}"
        lines.append(f"def {func_name}():")
        lines.append(f"    \"\"\"Covers: {criterion.covers}\"\"\"")
        for setup in compiler.setup_lines:
            lines.append(f"    {setup}")
        if compiler.exercise_line:
            lines.append(f"    {compiler.exercise_line}")
        for assertion in compiler.assert_lines:
            lines.append(f"    {assertion}")
        lines.append("")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Public library entry point (R-COMPILE-*, interface/library.md).
# ---------------------------------------------------------------------------

def compile(component_id: str, repo_root: Path, target: str = "pytest", out_dir: Path | None = None) -> CompileReport:
    if target not in SUPPORTED_TARGETS:
        raise ValueError(f"unsupported --target {target!r}")

    repo_root = Path(repo_root)
    slug = component_id[len("comp-"):] if component_id.startswith("comp-") else component_id
    acceptance_dir = repo_root / "specs" / "components" / slug / "acceptance"

    outputs: list[dict] = []
    compiled_count = 0
    error_count = 0
    skipped_count = 0

    surface: InterfaceSurface | None = None

    out_dir = Path(out_dir) if out_dir is not None else repo_root / "verification" / slug / "compiled"

    for path in sorted(acceptance_dir.glob("*.md")) if acceptance_dir.is_dir() else []:
        criterion = _parse_criterion_file(path)
        if criterion.kind != "compiled":
            skipped_count += 1
            continue

        if surface is None:
            surface = _load_interface_surface(repo_root, slug)

        try:
            scenarios = _split_scenarios(criterion.gherkin, start_line=1)
            if not scenarios:
                raise CompileError("no Given/When/Then steps found in gherkin block", criterion.file, 1)
            source = _emit_pytest(criterion, scenarios, surface)
        except CompileError as exc:
            error_count += 1
            outputs.append({
                "criterion_id": criterion.criterion_id,
                "covers": criterion.covers,
                "status": "error",
                "message": exc.message,
            })
            continue

        out_file = out_dir / f"test_{criterion.criterion_id.lower().replace('-', '_')}.py"
        # R-COMPILE-009: idempotent -- never touch an unchanged file.
        if not out_file.is_file() or out_file.read_text(encoding="utf-8") != source:
            out_file.parent.mkdir(parents=True, exist_ok=True)
            out_file.write_text(source, encoding="utf-8")
        compiled_count += 1
        try:
            file_label = str(out_file.relative_to(repo_root))
        except ValueError:
            file_label = str(out_file)
        outputs.append({
            "criterion_id": criterion.criterion_id,
            "covers": criterion.covers,
            "status": "compiled",
            "file": file_label,
        })

    return CompileReport(
        outputs=outputs,
        gate_version=GATE_VERSION,
        summary={
            "compiled": compiled_count,
            "errors": error_count,
            "skipped_non_compiled_kind": skipped_count,
        },
    )


# ---------------------------------------------------------------------------
# CLI (interface/cli.md).
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="hotdocs compile-criteria", add_help=True)
    parser.add_argument("component_id")
    parser.add_argument("--target", default="pytest")
    parser.add_argument("--out", default=None)
    parser.add_argument("--repo-root", default=None)

    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 2

    if args.target not in SUPPORTED_TARGETS:
        print(f"usage error: unsupported --target {args.target!r}", file=sys.stderr)
        return 2

    repo_root = Path(args.repo_root) if args.repo_root else Path.cwd()
    out_dir = Path(args.out) if args.out else None
    report = compile(args.component_id, repo_root, target=args.target, out_dir=out_dir)
    print(json.dumps(report.to_dict(), indent=2))
    return 1 if report.summary["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
