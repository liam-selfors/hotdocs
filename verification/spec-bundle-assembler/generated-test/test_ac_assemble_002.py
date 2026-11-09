import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import spec_bundle_assembler


def _field(obj, name):
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


GLOSSARY_MD = """# Glossary

- **Foo** — a test term.
"""

FOO_COMPONENT_MD = """---
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

Foo doubles a number. FOO_COMPONENT_MARKER_SHOULD_NOT_LEAK
"""

FOO_REQUIREMENT_MD = """# R-FOO-001

**R-FOO-001** — `foo(x)` MUST return `2 * x`. FOO_REQUIREMENT_MARKER_SHOULD_NOT_LEAK
"""

FOO_ACCEPTANCE_MD = """# AC-FOO-001

Covers: R-FOO-001
Kind: generated-test

```gherkin
Given x = 2
When foo(x) is called
Then it returns 4
```
"""

FOO_INTERFACE_LIBRARY_MD = """# Library

```python
def foo(x: int) -> int: ...
```

FOO_INTERFACE_MARKER_PRESENT
"""

FOO_CONSTRAINTS_MD = """# Constraints

None. FOO_CONSTRAINTS_MARKER_SHOULD_NOT_LEAK
"""

BAR_COMPONENT_MD = """---
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

Bar uses Foo to double numbers twice.
"""

BAR_REQUIREMENT_MD = """# R-BAR-001

**R-BAR-001** — `bar(x)` MUST return `4 * x`.
"""

BAR_ACCEPTANCE_MD = """# AC-BAR-001

Covers: R-BAR-001
Kind: generated-test

```gherkin
Given x = 2
When bar(x) is called
Then it returns 8
```
"""

BAR_INTERFACE_LIBRARY_MD = """# Library

```python
def bar(x: int) -> int: ...
```
"""

BAR_CONSTRAINTS_MD = """# Constraints

None.
"""


def test_dependency_interfaces_excludes_dependency_component_requirements_and_constraints():
    with TemporaryDirectory() as tmp:
        repo_root = Path(tmp)

        _write(repo_root / "specs" / "glossary.md", GLOSSARY_MD)

        foo_root = repo_root / "specs" / "components" / "foo"
        _write(foo_root / "component.md", FOO_COMPONENT_MD)
        _write(foo_root / "requirements" / "R-FOO-001.md", FOO_REQUIREMENT_MD)
        _write(foo_root / "acceptance" / "AC-FOO-001.md", FOO_ACCEPTANCE_MD)
        _write(foo_root / "interface" / "library.md", FOO_INTERFACE_LIBRARY_MD)
        _write(foo_root / "constraints.md", FOO_CONSTRAINTS_MD)

        bar_root = repo_root / "specs" / "components" / "bar"
        _write(bar_root / "component.md", BAR_COMPONENT_MD)
        _write(bar_root / "requirements" / "R-BAR-001.md", BAR_REQUIREMENT_MD)
        _write(bar_root / "acceptance" / "AC-BAR-001.md", BAR_ACCEPTANCE_MD)
        _write(bar_root / "interface" / "library.md", BAR_INTERFACE_LIBRARY_MD)
        _write(bar_root / "constraints.md", BAR_CONSTRAINTS_MD)

        bundle = spec_bundle_assembler.assemble("comp-bar", repo_root, mode="cold")

        dependency_interfaces = _field(bundle, "dependency_interfaces")
        assert dependency_interfaces is not None

        if not isinstance(dependency_interfaces, dict):
            dependency_interfaces = dict(dependency_interfaces)

        assert set(dependency_interfaces.keys()) == {"comp-foo"}

        foo_interface_content = dependency_interfaces["comp-foo"]
        assert isinstance(foo_interface_content, str)

        assert "FOO_INTERFACE_MARKER_PRESENT" in foo_interface_content

        assert "FOO_COMPONENT_MARKER_SHOULD_NOT_LEAK" not in foo_interface_content
        assert "FOO_REQUIREMENT_MARKER_SHOULD_NOT_LEAK" not in foo_interface_content
        assert "FOO_CONSTRAINTS_MARKER_SHOULD_NOT_LEAK" not in foo_interface_content


if __name__ == "__main__":
    test_dependency_interfaces_excludes_dependency_component_requirements_and_constraints()
    print("OK")