import spec_bundle_assembler


GLOSSARY_CONTENT = """# Glossary

- **Foo** — a test term.
"""

FOO_COMPONENT_CONTENT = """---
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

FOO_REQUIREMENT_CONTENT = """# R-FOO-001

**R-FOO-001** — `foo(x)` MUST return `2 * x`.
"""

FOO_ACCEPTANCE_CONTENT = """# AC-FOO-001

Covers: R-FOO-001
Kind: generated-test

```gherkin
Given x = 2
When foo(x) is called
Then it returns 4
```
"""

FOO_INTERFACE_CONTENT = """# Library

```
foo(x: int) -> int
```
"""

FOO_CONSTRAINTS_CONTENT = """# Constraints

None.
"""

BAR_COMPONENT_CONTENT = """---
id: comp-bar
title: Bar
status: draft
owners: [team-a]
sealed: true
source_path: legacy/bar/
depends_on: [comp-foo]
---

# Bar

## Purpose

Bar triples a number using Foo.
"""

BAR_REQUIREMENT_CONTENT = """# R-BAR-001

**R-BAR-001** — `bar(x)` MUST return `3 * x`.
"""

BAR_ACCEPTANCE_CONTENT = """# AC-BAR-001

Covers: R-BAR-001
Kind: generated-test

```gherkin
Given x = 2
When bar(x) is called
Then it returns 6
```
"""

BAR_INTERFACE_CONTENT = """# Library

```
bar(x: int) -> int
```
"""

BAR_CONSTRAINTS_CONTENT = """# Constraints

None.
"""


def _write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _field(obj, name):
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


def _build_corpus(repo_root):
    _write(repo_root / "specs" / "glossary.md", GLOSSARY_CONTENT)

    _write(repo_root / "specs" / "components" / "foo" / "component.md", FOO_COMPONENT_CONTENT)
    _write(
        repo_root / "specs" / "components" / "foo" / "requirements" / "R-FOO-001.md",
        FOO_REQUIREMENT_CONTENT,
    )
    _write(
        repo_root / "specs" / "components" / "foo" / "acceptance" / "AC-FOO-001.md",
        FOO_ACCEPTANCE_CONTENT,
    )
    _write(
        repo_root / "specs" / "components" / "foo" / "interface" / "library.md",
        FOO_INTERFACE_CONTENT,
    )
    _write(repo_root / "specs" / "components" / "foo" / "constraints.md", FOO_CONSTRAINTS_CONTENT)

    _write(repo_root / "specs" / "components" / "bar" / "component.md", BAR_COMPONENT_CONTENT)
    _write(
        repo_root / "specs" / "components" / "bar" / "requirements" / "R-BAR-001.md",
        BAR_REQUIREMENT_CONTENT,
    )
    _write(
        repo_root / "specs" / "components" / "bar" / "acceptance" / "AC-BAR-001.md",
        BAR_ACCEPTANCE_CONTENT,
    )
    _write(
        repo_root / "specs" / "components" / "bar" / "interface" / "library.md",
        BAR_INTERFACE_CONTENT,
    )
    _write(repo_root / "specs" / "components" / "bar" / "constraints.md", BAR_CONSTRAINTS_CONTENT)


def test_dependency_interfaces_contains_dependency_interface_text_only(tmp_path):
    repo_root = tmp_path
    _build_corpus(repo_root)

    bundle = spec_bundle_assembler.assemble_criterion("comp-bar", "AC-BAR-001", repo_root)

    assert _field(bundle, "component_id") == "comp-bar"
    assert _field(bundle, "criterion_id") == "AC-BAR-001"

    dependency_interfaces = _field(bundle, "dependency_interfaces")
    assert isinstance(dependency_interfaces, dict)
    assert "comp-foo" in dependency_interfaces

    foo_entry = dependency_interfaces["comp-foo"]

    assert "foo(x: int) -> int" in foo_entry
    assert "# Library" in foo_entry

    assert "Foo doubles a number." not in foo_entry
    assert "MUST return" not in foo_entry
    assert "2 * x" not in foo_entry
    assert "# Constraints" not in foo_entry
    assert "None." not in foo_entry.splitlines()


def test_dependency_interfaces_empty_mapping_when_no_depends_on(tmp_path):
    repo_root = tmp_path
    _build_corpus(repo_root)

    bundle = spec_bundle_assembler.assemble_criterion("comp-foo", "AC-FOO-001", repo_root)

    assert _field(bundle, "component_id") == "comp-foo"
    assert _field(bundle, "criterion_id") == "AC-FOO-001"

    dependency_interfaces = _field(bundle, "dependency_interfaces")
    assert dependency_interfaces is not None
    assert isinstance(dependency_interfaces, dict)
    assert dependency_interfaces == {}