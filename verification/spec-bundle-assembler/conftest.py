"""Synthetic fixture-corpus builder for spec-bundle-assembler's test
suite — needs precise control (a dependency with known Purpose/Rationale
text, a hard-fail-lint scenario, hint-mode gen/ content) the real corpus
can't give cleanly, mirroring spec-linter's own conftest.py pattern.
"""

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "gen" / "spec-bundle-assembler"))
sys.path.insert(0, str(REPO_ROOT / "gen" / "spec-linter"))
sys.path.insert(0, str(REPO_ROOT / "gen" / "graph-query-engine"))
import spec_bundle_assembler  # noqa: E402

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
---

# Foo

## Purpose

A minimal component for exercising the assembler.

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

A minimal capability for exercising the assembler.

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
FOO_LIBRARY = "# Library\n\n```\ndo_the_thing() -> None\n```\n"
FOO_DATA = "# `Thing`\n\n```json\n{\"id\": \"...\"}\n```\n"
FOO_ACCEPTANCE = "# AC-FOO-001\n\nCovers: R-FOO-001\nKind: compiled\n\n```gherkin\nGiven the component\nWhen do_the_thing is called\nThen it does the thing\n```\n"
CONSTRAINTS = "# {name} — Non-Functional Constraints\n\n- **Determinism.** MUST behave the same way every time.\n"


def _write_component(root: Path, name: str, component_md: str, requirement_name: str,
                      requirement_body: str, library_body: str, data_files: dict[str, str] | None = None) -> None:
    comp_dir = root / "specs" / "components" / name
    (comp_dir / "requirements").mkdir(parents=True, exist_ok=True)
    (comp_dir / "interface" / "data").mkdir(parents=True, exist_ok=True)
    (comp_dir / "acceptance").mkdir(parents=True, exist_ok=True)
    (comp_dir / "component.md").write_text(component_md)
    (comp_dir / "requirements" / requirement_name).write_text(requirement_body)
    (comp_dir / "interface" / "library.md").write_text(library_body)
    (comp_dir / "constraints.md").write_text(CONSTRAINTS.format(name=name.title()))
    for fname, content in (data_files or {}).items():
        (comp_dir / "interface" / "data" / fname).write_text(content)


def write_baseline(root: Path) -> None:
    (root / "specs" / "product").mkdir(parents=True, exist_ok=True)
    (root / "specs" / "vars").mkdir(parents=True, exist_ok=True)
    (root / "specs" / "glossary.md").write_text(GLOSSARY)
    (root / "specs" / "product" / "test-capability.md").write_text(PRODUCT)
    (root / "specs" / "vars" / "foo-url.md").write_text(VAR_FOO_URL)

    _write_component(root, "bar", BAR_COMPONENT, "R-BAR-001.md", BAR_REQUIREMENT, BAR_LIBRARY)
    (root / "specs" / "components" / "bar" / "acceptance" / "AC-BAR-001.md").write_text(
        "# AC-BAR-001\n\nCovers: R-BAR-001\nKind: compiled\n\n```gherkin\nGiven bar\nWhen bar_get runs\nThen it works\n```\n"
    )
    _write_component(root, "foo", FOO_COMPONENT, "R-FOO-001.md", FOO_REQUIREMENT, FOO_LIBRARY,
                      data_files={"Thing.md": FOO_DATA})
    (root / "specs" / "components" / "foo" / "acceptance" / "AC-FOO-001.md").write_text(FOO_ACCEPTANCE)


@pytest.fixture
def corpus_root(tmp_path):
    write_baseline(tmp_path)
    return tmp_path
