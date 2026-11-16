"""AC-IMPACT-005 (covers R-IMPACT-005).

Given P-ZERO-EDIT's capability scenarios changed, and comp-foo has
  realizes: [P-ZERO-EDIT]
When hotdocs impact --changed P-ZERO-EDIT runs
Then the report's impacted list contains comp-foo with reason
  "transitive-capability" and via "P-ZERO-EDIT"
"""

import importlib.util
import sys
from pathlib import Path

import pytest

import impact_analyzer


def _get(value, key, default=None):
    if isinstance(value, dict):
        return value.get(key, default)
    return getattr(value, key, default)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


PRODUCT_MD = """---
id: P-ZERO-EDIT
title: Zero edit capability
status: draft
owners: [alice]
---
# Zero edit capability

## Purpose

Lets a user complete a task without editing any file by hand.

## Scope

- In scope: completing a task with zero manual edits.
- Out of scope: everything else.

## Capability scenarios

### CS-ZERO-EDIT-001
Covers: P-ZERO-EDIT
Kind: generated-test

```gherkin
Given a fresh workspace
When the user completes a task
Then no file was edited by hand
```
"""

COMPONENT_MD = """---
id: comp-foo
title: Foo
status: draft
owners: [alice]
realizes: [P-ZERO-EDIT]
---
# Foo

## Purpose

Foo performs a small, self-contained task that contributes to completing work without manual edits.

## Rationale

Foo exists as a minimal example component for this fixture.

## Scope

- In scope: performing the foo task.
- Out of scope: anything else.

## Definitions

None.

## Behavior

See `requirements/`.

## Interfaces

See `interface/`.

## Data

None.

## Acceptance criteria

See `acceptance/`.

## Non-functional constraints

See `constraints.md`.

## Open questions

None.

## Change log

- Initial draft.
"""

REQUIREMENT_MD = """# R-FOO-001

**R-FOO-001** — The component MUST perform the foo task when `run_foo` is called.
"""

ACCEPTANCE_MD = """# AC-FOO-001

Covers: R-FOO-001
Kind: generated-test

```gherkin
Given a fresh workspace
When run_foo is called
Then the foo task has been performed
```
"""

LIBRARY_MD = """# Library

```
run_foo() -> None
```

Performs the foo task.
"""

CONSTRAINTS_MD = """# Constraints

- Latency: `run_foo` MUST return within 1 second, measured by timing a single call in a test.
"""

GLOSSARY_MD = """# Glossary

- **Foo task** — the small task the foo component performs.
"""


def _build_fixture(repo_root: Path) -> None:
    _write(repo_root / "specs" / "glossary.md", GLOSSARY_MD)
    _write(repo_root / "specs" / "product" / "zero-edit.md", PRODUCT_MD)
    comp = repo_root / "specs" / "components" / "foo"
    _write(comp / "component.md", COMPONENT_MD)
    _write(comp / "requirements" / "R-FOO-001.md", REQUIREMENT_MD)
    _write(comp / "acceptance" / "AC-FOO-001.md", ACCEPTANCE_MD)
    _write(comp / "interface" / "library.md", LIBRARY_MD)
    _write(comp / "constraints.md", CONSTRAINTS_MD)


def _candidate_linter_dirs(repo_root: Path):
    seen = set()
    starts = [repo_root]
    mod_file = getattr(impact_analyzer, "__file__", None)
    if mod_file:
        starts.append(Path(mod_file).resolve())
    starts.append(Path(__file__).resolve())
    starts.append(Path.cwd().resolve())
    for sp in starts:
        for parent in [sp] + list(sp.parents):
            d = parent / "gen" / "spec-linter"
            if d.is_dir() and d not in seen:
                seen.add(d)
                yield d


def _load_spec_linter(repo_root: Path):
    for d in _candidate_linter_dirs(repo_root):
        flat = d / "spec_linter.py"
        pkg_init = d / "spec_linter" / "__init__.py"
        module_name = "spec_linter"
        if flat.is_file():
            spec = importlib.util.spec_from_file_location(module_name, flat)
        elif pkg_init.is_file():
            spec = importlib.util.spec_from_file_location(
                module_name, pkg_init, submodule_search_locations=[str(pkg_init.parent)]
            )
        else:
            continue
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module  # register BEFORE exec_module
        spec.loader.exec_module(module)
        if hasattr(module, "lint"):
            return module
    return None


def _assert_lint_clean(repo_root: Path) -> None:
    spec_linter = _load_spec_linter(repo_root)
    if spec_linter is None:
        # The analyzer itself enforces the lint precondition; a non-clean
        # fixture will surface below as a non-null precondition_error.
        return
    report = spec_linter.lint(None, repo_root)
    findings = _get(report, "findings", []) or []
    hard = [f for f in findings if _get(f, "severity") == "fail"]
    msgs = [
        f"{_get(f, 'rule_id')} {_get(f, 'file')}:{_get(f, 'line')} {_get(f, 'message')}"
        for f in hard
    ]
    assert not hard, "fixture corpus is not lint-clean:\n" + "\n".join(msgs)


def test_ac_impact_005_capability_change_impacts_realizing_component(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root)

    _assert_lint_clean(repo_root)

    report = impact_analyzer.compute_blast_radius(["P-ZERO-EDIT"], repo_root)

    precondition_error = _get(report, "precondition_error")
    assert precondition_error is None, f"unexpected precondition_error: {precondition_error!r}"

    impacted = _get(report, "impacted", []) or []
    foo_entries = [e for e in impacted if _get(e, "component_id") == "comp-foo"]
    assert len(foo_entries) == 1, (
        f"expected exactly one comp-foo entry in impacted, got: {impacted!r}"
    )
    entry = foo_entries[0]
    assert _get(entry, "reason") == "transitive-capability", (
        f"expected reason 'transitive-capability', got {_get(entry, 'reason')!r}"
    )
    assert _get(entry, "via") == "P-ZERO-EDIT", (
        f"expected via 'P-ZERO-EDIT', got {_get(entry, 'via')!r}"
    )

    # component_id is always the full comp-<slug> form, never the bare slug.
    assert not any(_get(e, "component_id") == "foo" for e in impacted)