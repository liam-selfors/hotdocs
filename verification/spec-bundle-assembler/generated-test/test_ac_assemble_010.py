import spec_bundle_assembler

import dataclasses
import importlib.util
import json
import sys
from pathlib import Path


GLOSSARY = """# Glossary

- **Foo** — a test term.
"""

FOO_COMPONENT = """---
id: comp-foo
title: Foo
status: draft
owners: [team-a]
sealed: true
source_path: legacy/foo/
depends_on: [comp-bar]
---

# Foo

## Purpose

Foo doubles a number.
"""

BAR_COMPONENT = """---
id: comp-bar
title: Bar
status: draft
owners: [team-a]
sealed: true
source_path: legacy/bar/
depends_on: []
---

# Bar

## Purpose

Caches results.

## Rationale

Bar keeps a memo table per D13, trading memory for repeated lookup speed.
"""

D13_DECISION = """---
id: D13
title: Bar keeps a memo table
status: draft
owners: [team-a]
---

# D13: Bar keeps a memo table

## Context

Repeated lookups were slow.

## Decision

Bar keeps a memo table.

## Consequences

Bar uses more memory.
"""

RATIONALE_FRAGMENTS = [
    "D13",
    "memo table",
    "trading memory",
    "repeated lookup speed",
]


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_component(repo_root: Path, slug: str, component_md: str, upper: str, func: str, req_text: str) -> None:
    base = repo_root / "specs" / "components" / slug
    _write(base / "component.md", component_md)
    _write(
        base / "requirements" / f"R-{upper}-001.md",
        f"# R-{upper}-001\n\n**R-{upper}-001** — {req_text}\n",
    )
    _write(
        base / "acceptance" / f"AC-{upper}-001.md",
        f"# AC-{upper}-001\n"
        "\n"
        f"Covers: R-{upper}-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given x = 2\n"
        f"When {func}(x) is called\n"
        "Then it returns 4\n"
        "```\n",
    )
    _write(
        base / "interface" / "library.md",
        f"# Library\n\n```\n{func}(x: int) -> int\n```\n",
    )
    _write(base / "constraints.md", "# Constraints\n\nNone.\n")


def _build_corpus(repo_root: Path) -> None:
    _write(repo_root / "specs" / "glossary.md", GLOSSARY)
    _write_component(
        repo_root, "foo", FOO_COMPONENT, "FOO", "foo",
        "`foo(x)` MUST return `2 * x`.",
    )
    _write_component(
        repo_root, "bar", BAR_COMPONENT, "BAR", "bar",
        "`bar(x)` MUST return `2 * x`.",
    )
    _write(repo_root / "specs" / "decisions" / "D13.md", D13_DECISION)


def _load_spec_linter():
    gen = next(
        p for p in Path(spec_bundle_assembler.__file__).resolve().parents
        if p.name == "gen"
    )
    base = gen / "spec-linter"
    path = (
        base / "spec_linter.py"
        if (base / "spec_linter.py").is_file()
        else base / "spec_linter" / "__init__.py"
    )
    spec = importlib.util.spec_from_file_location("spec_linter", path)
    spec_linter = importlib.util.module_from_spec(spec)
    sys.modules["spec_linter"] = spec_linter
    spec.loader.exec_module(spec_linter)
    return spec_linter


def _bundle_text(bundle) -> str:
    names = [
        "component_id",
        "spec_bundle_hash",
        "spec",
        "interface",
        "constraints",
        "dependency_interfaces",
        "dependency_context",
        "dependency_usage",
        "vars",
        "glossary",
        "hint_code",
    ]
    parts = {}
    for name in names:
        try:
            parts[name] = field(bundle, name)
        except (KeyError, AttributeError):
            parts[name] = None
    text = json.dumps(parts, default=str, sort_keys=True)
    if dataclasses.is_dataclass(bundle) and not isinstance(bundle, type):
        try:
            text += json.dumps(dataclasses.asdict(bundle), default=str, sort_keys=True)
        except Exception:
            pass
    elif isinstance(bundle, dict):
        text += json.dumps(bundle, default=str, sort_keys=True)
    return text


def test_ac_assemble_010_dependency_context_is_purpose_only(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_corpus(repo_root)

    spec_linter = _load_spec_linter()
    report = spec_linter.lint(None, repo_root)
    hard = report["hard_failures"] if isinstance(report, dict) else report.hard_failures
    assert hard == 0

    bundle = spec_bundle_assembler.assemble("comp-foo", repo_root)

    dependency_context = field(bundle, "dependency_context")
    assert "comp-bar" in dependency_context
    assert dependency_context["comp-bar"] == "Caches results."

    text = _bundle_text(bundle)
    for fragment in RATIONALE_FRAGMENTS:
        assert fragment not in text, (
            f"Rationale content {fragment!r} leaked into the assembled bundle"
        )