import sys
from pathlib import Path

import pytest

import spec_bundle_assembler


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

GLOSSARY_MD = """# Glossary

- **Foo** — a test term.
"""

RULES_MD = """---
id: arch-rules
title: Rules
status: draft
owners: [team-a]
depends_on: []
---

# Rules

Foo rounds down.
"""

R_FOO_001_MD = """# R-FOO-001

**R-FOO-001** — `foo(x)` MUST return `2 * x`.
"""

AC_FOO_001_MD = """# AC-FOO-001

Covers: R-FOO-001
Kind: generated-test

```gherkin
Given x = 2
When foo(x) is called
Then it returns 4
```
"""

LIBRARY_MD = """# Library

```
foo(x: int) -> int
```

Implements: `specs/architecture/rules.md`
"""

LIBRARY_MD_MISSING = """# Library

```
foo(x: int) -> int
```

Implements: `specs/architecture/missing.md`
"""

CONSTRAINTS_MD = """# Constraints

None.
"""


def _build_repo(tmp_path, library_md, include_rules):
    repo_root = tmp_path / "repo"
    (repo_root / "specs").mkdir(parents=True)
    (repo_root / "specs" / "glossary.md").write_text(GLOSSARY_MD)

    if include_rules:
        arch_dir = repo_root / "specs" / "architecture"
        arch_dir.mkdir(parents=True)
        (arch_dir / "rules.md").write_text(RULES_MD)

    comp_dir = repo_root / "specs" / "components" / "foo"
    (comp_dir / "requirements").mkdir(parents=True)
    (comp_dir / "acceptance").mkdir(parents=True)
    (comp_dir / "interface").mkdir(parents=True)

    (comp_dir / "component.md").write_text(COMPONENT_MD)
    (comp_dir / "requirements" / "R-FOO-001.md").write_text(R_FOO_001_MD)
    (comp_dir / "acceptance" / "AC-FOO-001.md").write_text(AC_FOO_001_MD)
    (comp_dir / "interface" / "library.md").write_text(library_md)
    (comp_dir / "constraints.md").write_text(CONSTRAINTS_MD)

    return repo_root


def _load_spec_linter():
    import importlib.util

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


def _get_field(bundle, name):
    if isinstance(bundle, dict):
        return bundle.get(name)
    return getattr(bundle, name, None)


def test_implements_line_appends_architecture_doc_to_both_bundles(tmp_path):
    repo_root = _build_repo(tmp_path, LIBRARY_MD, include_rules=True)

    spec_linter = _load_spec_linter()
    report = spec_linter.lint(None, repo_root)
    assert report.hard_failures == 0

    rules_path = repo_root / "specs" / "architecture" / "rules.md"
    expected_doc_text = rules_path.read_text().rstrip("\n")

    spec_bundle = spec_bundle_assembler.assemble("comp-foo", repo_root)
    criterion_bundle = spec_bundle_assembler.assemble_criterion(
        "comp-foo", "AC-FOO-001", repo_root
    )

    marker = "\n## Implements: specs/architecture/rules.md\n\n"

    for bundle in (spec_bundle, criterion_bundle):
        interface_text = _get_field(bundle, "interface")
        assert isinstance(interface_text, str)

        idx = interface_text.find(marker)
        assert idx != -1, interface_text

        after = interface_text[idx + len(marker):]
        assert after.startswith(expected_doc_text)

        remainder = after[len(expected_doc_text):]
        assert remainder.strip() == ""


def test_missing_implements_target_raises_precondition_failure(tmp_path):
    repo_root = _build_repo(tmp_path, LIBRARY_MD_MISSING, include_rules=False)

    spec_linter = _load_spec_linter()
    report = spec_linter.lint(None, repo_root)
    assert report.hard_failures == 0

    with pytest.raises(spec_bundle_assembler.PreconditionFailure):
        spec_bundle_assembler.assemble("comp-foo", repo_root)