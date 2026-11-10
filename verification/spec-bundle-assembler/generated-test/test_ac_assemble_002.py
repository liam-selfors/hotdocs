import importlib.util
import sys
from pathlib import Path

import spec_bundle_assembler


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

Foo doubles a number.
"""

FOO_REQUIREMENT = """# R-FOO-001

**R-FOO-001** — `foo(x)` MUST return `2 * x`.
"""

FOO_ACCEPTANCE = """# AC-FOO-001

Covers: R-FOO-001
Kind: generated-test

```gherkin
Given x = 2
When foo(x) is called
Then it returns 4
```
"""

FOO_INTERFACE_LIBRARY = """# Library

```
foo(x: int) -> int
```
"""

FOO_CONSTRAINTS = """# Constraints

None.
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

Bar uses Foo to compute its own result.
"""

BAR_REQUIREMENT = """# R-BAR-001

**R-BAR-001** — `bar(x)` MUST return `foo(x) + 1`.
"""

BAR_ACCEPTANCE = """# AC-BAR-001

Covers: R-BAR-001
Kind: generated-test

```gherkin
Given x = 2
When bar(x) is called
Then it returns 5
```
"""

BAR_INTERFACE_LIBRARY = """# Library

```
bar(x: int) -> int
```
"""

BAR_CONSTRAINTS = """# Constraints

None.
"""

GLOSSARY = """# Glossary

- **Foo** — a test term.
"""


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _build_corpus(repo_root: Path) -> None:
    _write(repo_root / "specs" / "glossary.md", GLOSSARY)

    foo_root = repo_root / "specs" / "components" / "foo"
    _write(foo_root / "component.md", FOO_COMPONENT_MD)
    _write(foo_root / "requirements" / "R-FOO-001.md", FOO_REQUIREMENT)
    _write(foo_root / "acceptance" / "AC-FOO-001.md", FOO_ACCEPTANCE)
    _write(foo_root / "interface" / "library.md", FOO_INTERFACE_LIBRARY)
    _write(foo_root / "constraints.md", FOO_CONSTRAINTS)

    bar_root = repo_root / "specs" / "components" / "bar"
    _write(bar_root / "component.md", BAR_COMPONENT_MD)
    _write(bar_root / "requirements" / "R-BAR-001.md", BAR_REQUIREMENT)
    _write(bar_root / "acceptance" / "AC-BAR-001.md", BAR_ACCEPTANCE)
    _write(bar_root / "interface" / "library.md", BAR_INTERFACE_LIBRARY)
    _write(bar_root / "constraints.md", BAR_CONSTRAINTS)


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


def _field(value, name):
    return value.get(name) if isinstance(value, dict) else getattr(value, name, None)


def _assert_lint_clean(repo_root: Path) -> None:
    spec_linter = _load_spec_linter()
    report = spec_linter.lint(None, repo_root)
    hard_failures = _field(report, "hard_failures")
    if hard_failures is None:
        summary = _field(report, "summary")
        hard_failures = _field(summary, "hard_failures")
    assert hard_failures == 0


def _assert_only_interface_content(interface_text: str) -> None:
    assert "# Library" in interface_text
    assert "foo(x: int) -> int" in interface_text

    # component.md content (frontmatter and Purpose prose) must be absent.
    assert "## Purpose" not in interface_text
    assert "Foo doubles a number" not in interface_text
    assert "source_path" not in interface_text
    assert "depends_on" not in interface_text
    assert "sealed:" not in interface_text

    # requirements/ content must be absent.
    assert "R-FOO-001" not in interface_text
    assert "2 * x" not in interface_text

    # constraints.md content must be absent.
    assert "# Constraints" not in interface_text
    assert "None." not in interface_text


def test_assemble_dependency_interfaces_excludes_dependency_internals(tmp_path):
    repo_root = tmp_path / "repo"
    _build_corpus(repo_root)
    _assert_lint_clean(repo_root)

    bundle = spec_bundle_assembler.assemble("comp-bar", repo_root, mode="cold")

    dependency_interfaces = _field(bundle, "dependency_interfaces")
    assert dependency_interfaces is not None
    assert "comp-foo" in dependency_interfaces

    foo_interface_text = dependency_interfaces["comp-foo"]
    assert FOO_INTERFACE_LIBRARY.strip() in foo_interface_text

    _assert_only_interface_content(foo_interface_text)


def test_assemble_criterion_dependency_interfaces_excludes_dependency_internals(tmp_path):
    repo_root = tmp_path / "repo"
    _build_corpus(repo_root)
    _assert_lint_clean(repo_root)

    criterion_bundle = spec_bundle_assembler.assemble_criterion(
        "comp-bar", "AC-BAR-001", repo_root
    )

    dependency_interfaces = _field(criterion_bundle, "dependency_interfaces")
    assert dependency_interfaces is not None
    assert "comp-foo" in dependency_interfaces

    foo_interface_text = dependency_interfaces["comp-foo"]
    assert FOO_INTERFACE_LIBRARY.strip() in foo_interface_text

    _assert_only_interface_content(foo_interface_text)