import sys
import importlib.util
from pathlib import Path

import pytest

import spec_bundle_assembler


GLOSSARY_MD = """# Glossary

- **Foo** — a test term.
"""

COMPONENT_FOO_MD = """---
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

R_FOO_001_MD = """# R-FOO-001

**R-FOO-001** — `foo(x)` MUST return `2 * x`.
"""

# Deliberately missing the `Kind:` line — a hard spec-linter failure
# (per this criterion's fixture guidance), the one thing under test.
AC_FOO_001_BROKEN_MD = """# AC-FOO-001

Covers: R-FOO-001

```gherkin
Given x = 2
When foo(x) is called
Then it returns 4
```
"""

INTERFACE_FOO_MD = """# Library

```
foo(x: int) -> int
```
"""

COMPONENT_BAZ_MD = """---
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

Baz triples a number.
"""

R_BAZ_001_MD = """# R-BAZ-001

**R-BAZ-001** — `baz(x)` MUST return `3 * x`.
"""

AC_BAZ_001_MD = """# AC-BAZ-001

Covers: R-BAZ-001
Kind: generated-test

```gherkin
Given x = 2
When baz(x) is called
Then it returns 6
```
"""

INTERFACE_BAZ_MD = """# Library

```
baz(x: int) -> int
```
"""

CONSTRAINTS_MD = """# Constraints

None.
"""


def _write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _build_corpus_with_hard_fail(repo_root):
    _write(repo_root / "specs" / "glossary.md", GLOSSARY_MD)

    _write(repo_root / "specs" / "components" / "foo" / "component.md", COMPONENT_FOO_MD)
    _write(repo_root / "specs" / "components" / "foo" / "requirements" / "R-FOO-001.md", R_FOO_001_MD)
    _write(repo_root / "specs" / "components" / "foo" / "acceptance" / "AC-FOO-001.md", AC_FOO_001_BROKEN_MD)
    _write(repo_root / "specs" / "components" / "foo" / "interface" / "library.md", INTERFACE_FOO_MD)
    _write(repo_root / "specs" / "components" / "foo" / "constraints.md", CONSTRAINTS_MD)

    _write(repo_root / "specs" / "components" / "baz" / "component.md", COMPONENT_BAZ_MD)
    _write(repo_root / "specs" / "components" / "baz" / "requirements" / "R-BAZ-001.md", R_BAZ_001_MD)
    _write(repo_root / "specs" / "components" / "baz" / "acceptance" / "AC-BAZ-001.md", AC_BAZ_001_MD)
    _write(repo_root / "specs" / "components" / "baz" / "interface" / "library.md", INTERFACE_BAZ_MD)
    _write(repo_root / "specs" / "components" / "baz" / "constraints.md", CONSTRAINTS_MD)


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


def _hard_failures(report):
    return report.get("hard_failures") if isinstance(report, dict) else getattr(
        report, "hard_failures", None
    )


def test_assemble_fails_precondition_when_corpus_has_hard_fail_finding_anywhere(tmp_path):
    repo_root = tmp_path / "repo"
    _build_corpus_with_hard_fail(repo_root)

    spec_linter = _load_spec_linter()
    report = spec_linter.lint(None, repo_root)
    hard_failures = _hard_failures(report)
    assert hard_failures is not None and hard_failures >= 1

    # The hard-fail finding lives in comp-foo's acceptance file, but the
    # requirement says assembly must refuse for ANY component once the
    # corpus has a hard-fail finding anywhere in it — exercise both the
    # component that owns the broken doc and an unrelated clean one.
    for component_id in ("comp-foo", "comp-baz"):
        with pytest.raises(Exception):
            spec_bundle_assembler.assemble(component_id, repo_root)