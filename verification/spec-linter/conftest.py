"""Shared fixture-corpus builder for spec-linter's test suite.

Builds a minimal, otherwise-fully-valid spec corpus in a tmp directory, so
each AC-LINT-* test can mutate exactly one thing and assert exactly one rule
fires — rather than depending on this repository's real (and constantly
changing) spec corpus.

REWRITTEN for D15 (one-file-per-unit component layout): `foo`'s spec is now
`component.md` + `requirements/R-FOO-001.md` + `interface/library.md` +
`acceptance/AC-FOO-001.md` + `constraints.md`, replacing the original
`spec.md`/`interface.md`/`acceptance.md`/`constraints.md` flat files.
"""

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "gen" / "spec-linter"))
import spec_linter  # noqa: E402


GLOSSARY = """# Glossary

- **Widget** — a thing this corpus talks about.
"""

PRODUCT = """---
id: P-TEST
title: Test Capability
status: draft
owners: [test-team]
---

# Test Capability

## Purpose

A minimal capability for exercising the linter.

### CS-TEST-001
Covers: P-TEST
Kind: generated-test

```gherkin
Given a thing
When it happens
Then it works
```
"""

COMPONENT = """---
id: comp-foo
title: Foo
status: draft
owners: [test-team]
depends_on: []
realizes: [P-TEST]
sealed: false
---

# Foo

## Purpose

A minimal component for exercising the linter.

## Scope

In scope: everything. Out of scope: nothing.

## Definitions

No deltas from `specs/glossary.md`.

## Behavior

See `requirements/`.

## Interfaces

See `interface/`.

## Data

See `interface/data/`.

## Acceptance criteria

See `acceptance/`.

## Non-functional constraints

See `constraints.md`.

## Open questions

## Change log

- Initial draft.
"""

REQUIREMENT = """# R-FOO-001

**R-FOO-001** — The component MUST do the one thing it is specified to do.
"""

LIBRARY = """# Library

```
do_the_thing() -> None
```

Does the one thing.
"""

ACCEPTANCE = """# AC-FOO-001

Covers: R-FOO-001
Kind: compiled

```gherkin
Given the component
When do_the_thing is called
Then it does the thing
```
"""

CONSTRAINTS = """# Foo — Non-Functional Constraints

- **Determinism.** The component MUST behave the same way every time.
"""


def write_baseline(root: Path) -> None:
    comp_dir = root / "specs" / "components" / "foo"
    (root / "specs" / "product").mkdir(parents=True, exist_ok=True)
    (comp_dir / "requirements").mkdir(parents=True, exist_ok=True)
    (comp_dir / "interface" / "data").mkdir(parents=True, exist_ok=True)
    (comp_dir / "acceptance").mkdir(parents=True, exist_ok=True)

    (root / "specs" / "glossary.md").write_text(GLOSSARY)
    (root / "specs" / "product" / "test-capability.md").write_text(PRODUCT)
    (comp_dir / "component.md").write_text(COMPONENT)
    (comp_dir / "requirements" / "R-FOO-001.md").write_text(REQUIREMENT)
    (comp_dir / "interface" / "library.md").write_text(LIBRARY)
    (comp_dir / "acceptance" / "AC-FOO-001.md").write_text(ACCEPTANCE)
    (comp_dir / "constraints.md").write_text(CONSTRAINTS)


@pytest.fixture
def corpus_root(tmp_path):
    write_baseline(tmp_path)
    return tmp_path


def run_lint(root: Path, judge=None):
    return spec_linter.lint(None, root, judge=judge)


def has_finding(report, rule_id: str, severity: str = "fail") -> bool:
    return any(f.rule_id == rule_id and f.severity == severity for f in report.findings)
