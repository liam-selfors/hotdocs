import sys
import inspect
import importlib.util
import tempfile
from pathlib import Path

import spec_bundle_assembler


def _field(bundle, name):
    if isinstance(bundle, dict):
        return bundle.get(name)
    return getattr(bundle, name, None)


def test_dependency_usage_introspects_real_dependency_code():
    with tempfile.TemporaryDirectory() as tmp:
        repo_root = Path(tmp)

        (repo_root / "specs").mkdir(parents=True)
        (repo_root / "specs" / "glossary.md").write_text(
"""# Glossary

- **Foo** — a test term.
"""
        )

        foo_dir = repo_root / "specs" / "components" / "foo"
        (foo_dir / "requirements").mkdir(parents=True)
        (foo_dir / "acceptance").mkdir(parents=True)
        (foo_dir / "interface").mkdir(parents=True)

        (foo_dir / "component.md").write_text(
"""---
id: comp-foo
title: Foo
status: draft
owners: [team-a]
sealed: true
source_path: legacy/foo/
depends_on: [comp-bar, comp-baz]
---

# Foo

## Purpose

Foo uses bar and baz.
"""
        )

        (foo_dir / "requirements" / "R-FOO-001.md").write_text(
"""# R-FOO-001

**R-FOO-001** — `foo(x)` MUST return `2 * x`.
"""
        )

        (foo_dir / "acceptance" / "AC-FOO-001.md").write_text(
'''# AC-FOO-001

Covers: R-FOO-001
Kind: generated-test

```gherkin
Given x = 2
When foo(x) is called
Then it returns 4
```
'''
        )

        (foo_dir / "interface" / "library.md").write_text(
'''# Library

```
foo(x: int) -> int
```
'''
        )

        (foo_dir / "constraints.md").write_text(
"""# Constraints

None.
"""
        )

        bar_dir = repo_root / "specs" / "components" / "bar"
        (bar_dir / "requirements").mkdir(parents=True)
        (bar_dir / "acceptance").mkdir(parents=True)
        (bar_dir / "interface").mkdir(parents=True)

        (bar_dir / "component.md").write_text(
"""---
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

Bar gets values by key.
"""
        )

        (bar_dir / "requirements" / "R-BAR-001.md").write_text(
"""# R-BAR-001

**R-BAR-001** — `bar_get(key)` MUST return the value for `key`.
"""
        )

        (bar_dir / "acceptance" / "AC-BAR-001.md").write_text(
'''# AC-BAR-001

Covers: R-BAR-001
Kind: generated-test

```gherkin
Given key = "k"
When bar_get(key) is called
Then it returns "k"
```
'''
        )

        (bar_dir / "interface" / "library.md").write_text(
'''# Library

```
bar_get(key: str) -> str
```
'''
        )

        (bar_dir / "constraints.md").write_text(
"""# Constraints

None.
"""
        )

        baz_dir = repo_root / "specs" / "components" / "baz"
        (baz_dir / "requirements").mkdir(parents=True)
        (baz_dir / "acceptance").mkdir(parents=True)
        (baz_dir / "interface").mkdir(parents=True)

        (baz_dir / "component.md").write_text(
"""---
id: comp-baz
title: Baz
status: draft
owners: [team-a]
sealed: true
source_path: legacy/baz/
depends_on: []
---

# Baz

## Purpose

Baz is a spec-only dependency with no real code yet.
"""
        )

        (baz_dir / "requirements" / "R-BAZ-001.md").write_text(
"""# R-BAZ-001

**R-BAZ-001** — `baz()` MUST exist as a placeholder.
"""
        )

        (baz_dir / "acceptance" / "AC-BAZ-001.md").write_text(
'''# AC-BAZ-001

Covers: R-BAZ-001
Kind: generated-test

```gherkin
Given nothing
When baz is considered
Then it is a placeholder
```
'''
        )

        (baz_dir / "interface" / "library.md").write_text(
'''# Library

```
baz() -> None
```
'''
        )

        (baz_dir / "constraints.md").write_text(
"""# Constraints

None.
"""
        )

        bar_code_dir = repo_root / "legacy" / "bar"
        bar_code_dir.mkdir(parents=True)
        (bar_code_dir / "bar.py").write_text(
'''def bar_get(key: str) -> str:
    """Get a value by key.

    Looks up the stored value for the given key.
    """
    return key
'''
        )

        # comp-baz deliberately has no file under legacy/baz/ at all.

        gen = next(
            p for p in Path(spec_bundle_assembler.__file__).resolve().parents
            if p.name == "gen"
        )
        base = gen / "spec-linter"
        linter_path = (
            base / "spec_linter.py"
            if (base / "spec_linter.py").is_file()
            else base / "spec_linter" / "__init__.py"
        )
        spec = importlib.util.spec_from_file_location("spec_linter", linter_path)
        spec_linter = importlib.util.module_from_spec(spec)
        sys.modules["spec_linter"] = spec_linter
        spec.loader.exec_module(spec_linter)
        assert spec_linter.lint(None, repo_root).hard_failures == 0

        bundle = spec_bundle_assembler.assemble("comp-foo", repo_root, mode="cold")

        dependency_usage = _field(bundle, "dependency_usage")
        assert dependency_usage is not None

        usage_bar = dependency_usage["comp-bar"]

        def _bar_get_reference(key: str) -> str:
            """Get a value by key.

            Looks up the stored value for the given key.
            """
            return key

        expected_signature = str(inspect.signature(_bar_get_reference))
        expected_docstring_first_line = _bar_get_reference.__doc__.splitlines()[0].strip()

        assert "bar" in usage_bar
        assert "legacy/bar/" in usage_bar
        assert "bar_get" in usage_bar
        assert expected_signature in usage_bar
        assert expected_docstring_first_line in usage_bar

        usage_baz = dependency_usage["comp-baz"]
        assert usage_baz == ""