import pytest

import spec_bundle_assembler


def _get(obj, key):
    return obj.get(key) if isinstance(obj, dict) else getattr(obj, key, None)


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

GLOSSARY_MD = """# Glossary

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

CONSTRAINTS_MD = """# Constraints

None.
"""


def _library_md(implements_path):
    return (
        "# Library\n"
        "\n"
        "```\n"
        "foo(x: int) -> int\n"
        "```\n"
        "\n"
        "Implements: `{}`\n"
    ).format(implements_path)


def _build_fixture(repo_root, implements_path, include_rules_file=True):
    (repo_root / "specs" / "glossary.md").parent.mkdir(parents=True, exist_ok=True)
    (repo_root / "specs" / "glossary.md").write_text(GLOSSARY_MD)

    if include_rules_file:
        rules_path = repo_root / "specs" / "architecture" / "rules.md"
        rules_path.parent.mkdir(parents=True, exist_ok=True)
        rules_path.write_text(RULES_MD)

    comp_root = repo_root / "specs" / "components" / "foo"

    (comp_root).mkdir(parents=True, exist_ok=True)
    (comp_root / "component.md").write_text(COMPONENT_MD)

    (comp_root / "requirements").mkdir(parents=True, exist_ok=True)
    (comp_root / "requirements" / "R-FOO-001.md").write_text(REQUIREMENT_MD)

    (comp_root / "acceptance").mkdir(parents=True, exist_ok=True)
    (comp_root / "acceptance" / "AC-FOO-001.md").write_text(ACCEPTANCE_MD)

    (comp_root / "interface").mkdir(parents=True, exist_ok=True)
    (comp_root / "interface" / "library.md").write_text(_library_md(implements_path))

    (comp_root / "constraints.md").write_text(CONSTRAINTS_MD)


def test_implements_line_appends_full_document_text(tmp_path):
    repo_root = tmp_path
    _build_fixture(repo_root, "specs/architecture/rules.md")

    rules_full_text = (repo_root / "specs" / "architecture" / "rules.md").read_text()
    marker = "## Implements: specs/architecture/rules.md"

    bundle = spec_bundle_assembler.assemble("comp-foo", repo_root)
    interface = _get(bundle, "interface")

    assert marker in interface

    stripped_interface = interface.rstrip()
    stripped_rules_text = rules_full_text.rstrip()

    assert stripped_interface.endswith(stripped_rules_text)

    marker_idx = interface.index(marker)
    rules_start_idx = len(stripped_interface) - len(stripped_rules_text)
    assert marker_idx < rules_start_idx

    cbundle = spec_bundle_assembler.assemble_criterion(
        "comp-foo", "AC-FOO-001", repo_root
    )
    criterion_interface = _get(cbundle, "interface")

    assert marker in criterion_interface

    stripped_criterion_interface = criterion_interface.rstrip()
    assert stripped_criterion_interface.endswith(stripped_rules_text)

    criterion_marker_idx = criterion_interface.index(marker)
    criterion_rules_start_idx = len(stripped_criterion_interface) - len(
        stripped_rules_text
    )
    assert criterion_marker_idx < criterion_rules_start_idx


def test_implements_line_naming_missing_document_raises_precondition_failure(
    tmp_path,
):
    repo_root = tmp_path
    _build_fixture(
        repo_root, "specs/architecture/missing.md", include_rules_file=False
    )

    missing_path = repo_root / "specs" / "architecture" / "missing.md"
    assert not missing_path.exists()

    with pytest.raises(spec_bundle_assembler.PreconditionFailure):
        spec_bundle_assembler.assemble("comp-foo", repo_root)