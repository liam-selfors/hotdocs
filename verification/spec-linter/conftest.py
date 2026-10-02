"""Shared fixture-corpus builder for spec-linter's test suite.

Builds a minimal, otherwise-fully-valid spec corpus in a tmp directory, so
each AC-LINT-* test can mutate exactly one thing and assert exactly one rule
fires — rather than depending on this repository's real (and constantly
changing) spec corpus.
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

### GS-TEST-001
Covers: P-TEST
Kind: generated-test

```gherkin
Given a thing
When it happens
Then it works
```
"""

SPEC = """---
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

- **R-FOO-001** — The component MUST do the one thing it is specified to do.

## Interfaces

See `interface.md`.

## Data

None.

## Acceptance criteria

See `acceptance.md`.

## Non-functional constraints

See `constraints.md`.

## Open questions

## Change log

- Initial draft.
"""

INTERFACE = """---
id: comp-foo-interface
title: Foo — Interface
status: draft
owners: [test-team]
---

# Foo — Interface

- `do_the_thing()` — does the one thing.
"""

ACCEPTANCE = """---
id: comp-foo-acceptance
title: Foo — Acceptance Criteria
status: draft
owners: [test-team]
---

# Foo — Acceptance Criteria

### AC-FOO-001
Covers: R-FOO-001
Kind: compiled

```gherkin
Given the component
When do_the_thing is called
Then it does the thing
```
"""

CONSTRAINTS = """---
id: comp-foo-constraints
title: Foo — Non-Functional Constraints
status: draft
owners: [test-team]
---

# Foo — Non-Functional Constraints

- **Determinism.** The component MUST behave the same way every time.
"""


def write_baseline(root: Path) -> None:
    (root / "specs" / "product").mkdir(parents=True, exist_ok=True)
    (root / "specs" / "components" / "foo").mkdir(parents=True, exist_ok=True)
    (root / "specs" / "glossary.md").write_text(GLOSSARY)
    (root / "specs" / "product" / "test-capability.md").write_text(PRODUCT)
    (root / "specs" / "components" / "foo" / "spec.md").write_text(SPEC)
    (root / "specs" / "components" / "foo" / "interface.md").write_text(INTERFACE)
    (root / "specs" / "components" / "foo" / "acceptance.md").write_text(ACCEPTANCE)
    (root / "specs" / "components" / "foo" / "constraints.md").write_text(CONSTRAINTS)


@pytest.fixture
def corpus_root(tmp_path):
    write_baseline(tmp_path)
    return tmp_path


def run_lint(root: Path, judge=None):
    return spec_linter.lint(None, root, judge=judge)


def has_finding(report, rule_id: str, severity: str = "fail") -> bool:
    return any(f.rule_id == rule_id and f.severity == severity for f in report.findings)
