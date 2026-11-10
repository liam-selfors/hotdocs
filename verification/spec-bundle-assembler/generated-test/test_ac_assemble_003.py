import importlib.util
import sys
from pathlib import Path

import spec_bundle_assembler


def _field(obj, name):
    return obj.get(name) if isinstance(obj, dict) else getattr(obj, name, None)


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


def _write_fixture(repo_root: Path) -> None:
    (repo_root / "specs").mkdir(parents=True, exist_ok=True)
    (repo_root / "specs" / "glossary.md").write_text(
        """# Glossary

- **Foo** — a test term.
"""
    )

    comp_dir = repo_root / "specs" / "components" / "foo"
    (comp_dir / "requirements").mkdir(parents=True, exist_ok=True)
    (comp_dir / "acceptance").mkdir(parents=True, exist_ok=True)
    (comp_dir / "interface").mkdir(parents=True, exist_ok=True)

    (comp_dir / "component.md").write_text(
        """---
id: comp-foo
title: Foo
status: draft
owners: [team-a]
sealed: true
source_path: legacy/foo/
depends_on: []
uses_var: [VAR-FOO-URL]
---

# Foo

## Purpose

Foo doubles a number.
"""
    )

    (comp_dir / "requirements" / "R-FOO-001.md").write_text(
        """# R-FOO-001

**R-FOO-001** — `foo(x)` MUST return `2 * x`.
"""
    )

    (comp_dir / "acceptance" / "AC-FOO-001.md").write_text(
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

    (comp_dir / "interface" / "library.md").write_text(
        """# Library

```
foo(x: int) -> int
```
"""
    )

    (comp_dir / "constraints.md").write_text(
        """# Constraints

None.
"""
    )

    vars_dir = repo_root / "specs" / "vars"
    vars_dir.mkdir(parents=True, exist_ok=True)
    (vars_dir / "VAR-FOO-URL.md").write_text(
        """---
id: VAR-FOO-URL
title: Foo Service URL
status: draft
owners: [team-a]
type: string
required: true
sensitivity: low
---

# VAR-FOO-URL

## Description

The URL of the foo service that comp-foo calls.
"""
    )


def test_ac_assemble_003_vars_field_contains_full_var_declaration(tmp_path):
    repo_root = tmp_path / "repo"
    _write_fixture(repo_root)

    spec_linter = _load_spec_linter()
    report = spec_linter.lint(None, repo_root)
    assert report.hard_failures == 0

    bundle = spec_bundle_assembler.assemble("comp-foo", repo_root, mode="cold")

    vars_field = _field(bundle, "vars")
    assert vars_field is not None
    assert "VAR-FOO-URL" in vars_field

    var_content = vars_field["VAR-FOO-URL"]

    assert "VAR-FOO-URL" in var_content
    assert "type: string" in var_content
    assert "required: true" in var_content
    assert "sensitivity: low" in var_content
    assert "The URL of the foo service that comp-foo calls." in var_content