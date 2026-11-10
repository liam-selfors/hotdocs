import importlib.util
import sys
from pathlib import Path

import pytest

import spec_bundle_assembler

GLOSSARY_CONTENT = """# Glossary

- **Foo** — a test term.
"""

COMPONENT_MD = """---
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

Foo doubles a number.
"""

REQUIREMENT_MD = """# R-FOO-001

**R-FOO-001** — `foo(x)` MUST return `2 * x`.
"""

ACCEPTANCE_MD = """# AC-FOO-001

Covers: R-FOO-001
Kind: generated-test

```gherkin
Given x = 2
When foo(x) is called
Then it returns 4
```
"""

INTERFACE_LIBRARY_MD = """# Library

```
foo(x: int) -> int
```
"""

CONSTRAINTS_MD = """# Constraints

None.
"""


def _build_repo(repo_root: Path) -> None:
    (repo_root / "specs").mkdir(parents=True)
    (repo_root / "specs" / "glossary.md").write_text(GLOSSARY_CONTENT)

    comp_root = repo_root / "specs" / "components" / "foo"
    comp_root.mkdir(parents=True)
    (comp_root / "component.md").write_text(COMPONENT_MD)

    (comp_root / "requirements").mkdir()
    (comp_root / "requirements" / "R-FOO-001.md").write_text(REQUIREMENT_MD)

    (comp_root / "acceptance").mkdir()
    (comp_root / "acceptance" / "AC-FOO-001.md").write_text(ACCEPTANCE_MD)

    (comp_root / "interface").mkdir()
    (comp_root / "interface" / "library.md").write_text(INTERFACE_LIBRARY_MD)

    (comp_root / "constraints.md").write_text(CONSTRAINTS_MD)


def _load_spec_linter():
    gen = next(
        p
        for p in Path(spec_bundle_assembler.__file__).resolve().parents
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


def test_assemble_glossary_field_matches_glossary_md_exactly(tmp_path):
    repo_root = tmp_path / "repo"
    _build_repo(repo_root)

    spec_linter = _load_spec_linter()
    report = spec_linter.lint(None, repo_root)
    assert report.hard_failures == 0

    bundle = spec_bundle_assembler.assemble("comp-foo", repo_root, mode="cold")

    glossary_field = (
        bundle.get("glossary")
        if isinstance(bundle, dict)
        else getattr(bundle, "glossary", None)
    )

    on_disk_glossary = (repo_root / "specs" / "glossary.md").read_text()

    assert glossary_field == on_disk_glossary
    assert glossary_field == GLOSSARY_CONTENT


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__]))