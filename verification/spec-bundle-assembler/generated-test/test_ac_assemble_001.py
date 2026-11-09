from pathlib import Path

import spec_bundle_assembler


def _get_field(bundle, name, default=None):
    if isinstance(bundle, dict):
        return bundle.get(name, default)
    return getattr(bundle, name, default)


def _write_fixture(repo_root: Path) -> None:
    glossary_md = """# Glossary

- **Foo** — a test term.
"""

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

Foo doubles a number.
"""

    requirement_md = """# R-FOO-001

**R-FOO-001** — `foo(x)` MUST return `2 * x`.
"""

    interface_library_md = """# Library

```
foo(x: int) -> int
```
"""

    constraints_md = """# Constraints

None.
"""

    acceptance_md = """# AC-FOO-001

Covers: R-FOO-001
Kind: generated-test

```gherkin
Given x = 2
When foo(x) is called
Then it returns 4
```
"""

    comp_dir = repo_root / "specs" / "components" / "foo"
    (repo_root / "specs").mkdir(parents=True, exist_ok=True)
    (repo_root / "specs" / "glossary.md").write_text(glossary_md)

    comp_dir.mkdir(parents=True, exist_ok=True)
    (comp_dir / "component.md").write_text(component_md)

    (comp_dir / "requirements").mkdir(parents=True, exist_ok=True)
    (comp_dir / "requirements" / "R-FOO-001.md").write_text(requirement_md)

    (comp_dir / "interface").mkdir(parents=True, exist_ok=True)
    (comp_dir / "interface" / "library.md").write_text(interface_library_md)

    (comp_dir / "constraints.md").write_text(constraints_md)

    (comp_dir / "acceptance").mkdir(parents=True, exist_ok=True)
    (comp_dir / "acceptance" / "AC-FOO-001.md").write_text(acceptance_md)


def test_ac_assemble_001_cold_bundle_excludes_acceptance(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write_fixture(repo_root)

    bundle = spec_bundle_assembler.assemble("comp-foo", repo_root, mode="cold")

    spec_value = _get_field(bundle, "spec")
    interface_value = _get_field(bundle, "interface")
    constraints_value = _get_field(bundle, "constraints")

    assert spec_value is not None
    assert interface_value is not None
    assert constraints_value is not None

    assert "Foo doubles a number." in spec_value
    assert "MUST return" in spec_value
    assert "2 * x" in spec_value

    assert "foo(x: int) -> int" in interface_value

    assert "None." in constraints_value

    acceptance_markers = [
        "AC-FOO-001",
        "Given x = 2",
        "it returns 4",
        "generated-test",
    ]

    documented_field_names = [
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

    for field_name in documented_field_names:
        field_value = _get_field(bundle, field_name)
        field_text = str(field_value) if field_value is not None else ""
        for marker in acceptance_markers:
            assert marker not in field_text, (
                "field %r unexpectedly contains acceptance-derived marker %r"
                % (field_name, marker)
            )

    assert _get_field(bundle, "hint_code") is None