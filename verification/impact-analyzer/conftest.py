"""Synthetic fixture-corpus + real git repo builder for impact-analyzer's
test suite -- adapted from spec-bundle-assembler's own conftest.py (the
same lint-clean baseline), since impact-analyzer also calls
spec_linter.lint() as a real precondition check (R-IMPACT-007) and, since
D64, resolves "the prior commit" via real git history (R-IMPACT-010)."""

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "gen" / "impact-analyzer"))
sys.path.insert(0, str(REPO_ROOT / "gen" / "spec-linter"))
import impact_analyzer  # noqa: E402

GLOSSARY = "# Glossary\n\n- **Widget** — a thing this corpus talks about.\n"

VAR_FOO_URL = (
    "---\nid: VAR-FOO-URL\ntitle: Foo URL\nstatus: draft\nowners: [test-team]\n---\n\n"
    "# VAR-FOO-URL\n\n- **required:** no\n- **type:** url\n"
    "- **sensitivity:** non-secret\n- **description:** Where foo lives.\n"
)

BAR_COMPONENT = """---
id: comp-bar
title: Bar
status: draft
owners: [test-team]
depends_on: []
realizes: [P-TEST]
sealed: false
---

# Bar

## Purpose

Caches results.

## Rationale

Backs D13's "cache every gate" mandate.

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

FOO_COMPONENT = """---
id: comp-foo
title: Foo
status: draft
owners: [test-team]
depends_on: [comp-bar]
realizes: [P-TEST]
uses_var: [VAR-FOO-URL]
sealed: false
{extra}---

# Foo

## Purpose

A minimal component for exercising the analyzer.

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

PRODUCT = """---
id: P-TEST
title: Test Capability
status: draft
owners: [test-team]
---

# Test Capability

## Purpose

A minimal capability for exercising the analyzer.

### CS-TEST-001
Covers: P-TEST
Kind: generated-test

```gherkin
Given a thing
When it happens
Then it works
```
"""

BAR_REQUIREMENT = "# R-BAR-001\n\n**R-BAR-001** — Bar MUST cache things.\n"
FOO_REQUIREMENT = "# R-FOO-001\n\n**R-FOO-001** — Foo MUST do the one thing it is specified to do.\n"
BAR_LIBRARY = "# Library\n\n```\nbar_get(key: str) -> str\n```\n"
FOO_LIBRARY_V1 = "# Library\n\n```\ndo_the_thing() -> None\n```\n"
FOO_LIBRARY_V2 = "# Library\n\n```\ndo_the_thing() -> None\ndo_another_thing() -> None\n```\n"
FOO_DATA = "# `Thing`\n\n```json\n{\"id\": \"...\"}\n```\n"
FOO_ACCEPTANCE = "# AC-FOO-001\n\nCovers: R-FOO-001\nKind: generated-test\n\n```gherkin\nGiven the component\nWhen do_the_thing is called\nThen it does the thing\n```\n"
BAR_ACCEPTANCE = "# AC-BAR-001\n\nCovers: R-BAR-001\nKind: generated-test\n\n```gherkin\nGiven bar\nWhen bar_get runs\nThen it works\n```\n"
CONSTRAINTS = "# {name} — Non-Functional Constraints\n\n- **Determinism.** MUST behave the same way every time.\n"

GUARANTEE_TEMPLATE = "# {gid}\n\n**{gid}** — Bar MUST guarantee this behavior holds.\n"


def write_baseline(root: Path, bar_guarantees: dict[str, str] | None = None, foo_depends_on_guarantees: list[str] | None = None) -> None:
    (root / "specs" / "product").mkdir(parents=True, exist_ok=True)
    (root / "specs" / "vars").mkdir(parents=True, exist_ok=True)
    (root / "specs" / "glossary.md").write_text(GLOSSARY)
    (root / "specs" / "product" / "test-capability.md").write_text(PRODUCT)
    (root / "specs" / "vars" / "foo-url.md").write_text(VAR_FOO_URL)

    bar_dir = root / "specs" / "components" / "bar"
    (bar_dir / "requirements").mkdir(parents=True, exist_ok=True)
    (bar_dir / "interface" / "data").mkdir(parents=True, exist_ok=True)
    (bar_dir / "acceptance").mkdir(parents=True, exist_ok=True)
    (bar_dir / "component.md").write_text(BAR_COMPONENT)
    (bar_dir / "requirements" / "R-BAR-001.md").write_text(BAR_REQUIREMENT)
    (bar_dir / "interface" / "library.md").write_text(BAR_LIBRARY)
    (bar_dir / "constraints.md").write_text(CONSTRAINTS.format(name="Bar"))
    (bar_dir / "acceptance" / "AC-BAR-001.md").write_text(BAR_ACCEPTANCE)
    if bar_guarantees:
        (bar_dir / "interface" / "guarantees").mkdir(parents=True, exist_ok=True)
        for gid, body in bar_guarantees.items():
            (bar_dir / "interface" / "guarantees" / f"{gid}.md").write_text(body)

    extra = ""
    if foo_depends_on_guarantees:
        gl = ", ".join(foo_depends_on_guarantees)
        extra = f"depends_on_guarantees: [{gl}]\n"
    foo_dir = root / "specs" / "components" / "foo"
    (foo_dir / "requirements").mkdir(parents=True, exist_ok=True)
    (foo_dir / "interface" / "data").mkdir(parents=True, exist_ok=True)
    (foo_dir / "acceptance").mkdir(parents=True, exist_ok=True)
    (foo_dir / "component.md").write_text(FOO_COMPONENT.format(extra=extra))
    (foo_dir / "requirements" / "R-FOO-001.md").write_text(FOO_REQUIREMENT)
    (foo_dir / "interface" / "library.md").write_text(FOO_LIBRARY_V1)
    (foo_dir / "interface" / "data" / "Thing.md").write_text(FOO_DATA)
    (foo_dir / "constraints.md").write_text(CONSTRAINTS.format(name="Foo"))
    (foo_dir / "acceptance" / "AC-FOO-001.md").write_text(FOO_ACCEPTANCE)


def _git(repo_root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=repo_root, capture_output=True, text=True, check=True)


def init_git_repo(root: Path) -> None:
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "test@example.com")
    _git(root, "config", "user.name", "Test")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "baseline")


def commit_all(root: Path, message: str) -> None:
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", message)


def checkout_new_branch(root: Path, name: str) -> None:
    _git(root, "checkout", "-q", "-b", name)


@pytest.fixture
def git_repo(tmp_path):
    """A real git repo with the baseline corpus committed on `main`, then
    HEAD moved to a new `feature` branch -- so git merge-base(HEAD, main)
    resolves to that baseline commit (R-IMPACT-010), and any further
    commit on `feature` is "relative to the prior commit" from there."""
    write_baseline(tmp_path)
    init_git_repo(tmp_path)
    checkout_new_branch(tmp_path, "feature")
    return tmp_path
