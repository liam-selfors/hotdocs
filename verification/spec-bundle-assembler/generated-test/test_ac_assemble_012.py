import importlib.util
import sys
from pathlib import Path

import spec_bundle_assembler


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def test_ac_assemble_012(tmp_path):
    repo_root = tmp_path

    glossary_md = """# Glossary

- **Foo** — a test term.
"""
    _write(repo_root / "specs" / "glossary.md", glossary_md)

    component_md = """---
id: comp-foo
title: Foo
status: draft
owners: [team-a]
sealed: true
source_path: legacy/foo/
depends_on: []
---

# Foo

## Purpose

Foo doubles a number. PURPOSE_MARKER_TEXT_12345.

## Scope

Foo operates only on integers. SCOPE_MARKER_TEXT_67890.

## Rationale

RATIONALE_MARKER_TEXT_ABCDE because we decided so in the past.

## Open questions

OPEN_QUESTIONS_MARKER_TEXT_FGHIJ - should we support floats?

## Change log

CHANGE_LOG_MARKER_TEXT_KLMNO - initial version.
"""
    _write(repo_root / "specs" / "components" / "foo" / "component.md", component_md)

    requirement_md = """# R-FOO-001

**R-FOO-001** — `foo(x)` MUST return `2 * x`.
"""
    _write(
        repo_root / "specs" / "components" / "foo" / "requirements" / "R-FOO-001.md",
        requirement_md,
    )

    acceptance_md = """# AC-FOO-001

Covers: R-FOO-001
Kind: generated-test

```gherkin
Given x = 2
When foo(x) is called
Then it returns 4
```
"""
    _write(
        repo_root / "specs" / "components" / "foo" / "acceptance" / "AC-FOO-001.md",
        acceptance_md,
    )

    interface_md = """# Library

```
foo(x: int) -> int
```
"""
    _write(
        repo_root / "specs" / "components" / "foo" / "interface" / "library.md",
        interface_md,
    )

    constraints_md = """# Constraints

None.
"""
    _write(
        repo_root / "specs" / "components" / "foo" / "constraints.md",
        constraints_md,
    )

    gen = next(
        p
        for p in Path(spec_bundle_assembler.__file__).resolve().parents
        if p.name == "gen"
    )
    base = gen / "spec-linter"
    lint_path = (
        base / "spec_linter.py"
        if (base / "spec_linter.py").is_file()
        else base / "spec_linter" / "__init__.py"
    )
    lint_spec = importlib.util.spec_from_file_location("spec_linter", lint_path)
    spec_linter = importlib.util.module_from_spec(lint_spec)
    sys.modules["spec_linter"] = spec_linter
    lint_spec.loader.exec_module(spec_linter)

    report = spec_linter.lint(None, repo_root)
    assert report.hard_failures == 0

    bundle = spec_bundle_assembler.assemble("comp-foo", repo_root, mode="cold")

    spec_text = bundle.get("spec") if isinstance(bundle, dict) else getattr(bundle, "spec", None)
    assert spec_text is not None

    assert "PURPOSE_MARKER_TEXT_12345" in spec_text
    assert "SCOPE_MARKER_TEXT_67890" in spec_text

    assert "RATIONALE_MARKER_TEXT_ABCDE" not in spec_text
    assert "OPEN_QUESTIONS_MARKER_TEXT_FGHIJ" not in spec_text
    assert "CHANGE_LOG_MARKER_TEXT_KLMNO" not in spec_text