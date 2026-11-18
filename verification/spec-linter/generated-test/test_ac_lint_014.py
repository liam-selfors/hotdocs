# hotdocs-criterion: sha256:1cd2506c2c779d3c7b8aab44f2696294f0a8ac59b0501a460f5a40a5d199163e
import json
from pathlib import Path

import pytest

import spec_linter


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


COMPONENT_MD = """---
id: comp-foo
title: Foo
status: draft
owners: [test-team]
sealed: true
source_path: legacy/foo/
---

# Foo

## Purpose

Foo does one small thing for the test fixture.

## Scope

- In scope: the one small thing.
- Out of scope: everything else.

## Definitions

None.

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

REQUIREMENT_MD = """# R-FOO-001

**R-FOO-001** — Foo MUST do the one small thing.
"""

ACCEPTANCE_MD = """# AC-FOO-001

Covers: R-FOO-001
Kind: compiled

```gherkin
Given a foo
When it runs
Then it does the one small thing
```
"""

CONSTRAINTS_MD = """# Constraints

- None beyond the defaults.
"""

PRIMARY_GLOSSARY = """# Glossary

Canonical vocabulary for this spec corpus. Specs **MUST** use these terms as
defined.

- **Widget** — a small thing the corpus talks about.
"""

SECOND_GLOSSARY = """# Glossary

Canonical vocabulary for this spec corpus. Specs **MUST** use these terms as
defined.

- **Invoice** — a billing document the corpus talks about.
"""


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_corpus(root: Path, second_glossary: bool) -> Path:
    specs = root / "specs"
    for sub in ("product", "architecture", "vars", "decisions"):
        (specs / sub).mkdir(parents=True, exist_ok=True)
    comp = specs / "components" / "foo"
    _write(comp / "component.md", COMPONENT_MD)
    _write(comp / "requirements" / "R-FOO-001.md", REQUIREMENT_MD)
    _write(comp / "acceptance" / "AC-FOO-001.md", ACCEPTANCE_MD)
    _write(comp / "constraints.md", CONSTRAINTS_MD)
    _write(specs / "glossary.md", PRIMARY_GLOSSARY)
    if second_glossary:
        _write(specs / "glossary-billing.md", SECOND_GLOSSARY)
    return root


def _lint014_fails(report):
    findings = field(report, "findings")
    return [
        f
        for f in findings
        if field(f, "rule_id") == "R-LINT-014" and field(f, "severity") == "fail"
    ]


def test_two_glossaries_without_split_decision_fail_r_lint_014(tmp_path):
    root = _build_corpus(tmp_path / "repo", second_glossary=True)

    report = spec_linter.lint(None, root)

    matches = _lint014_fails(report)
    assert matches, (
        "expected a fail-severity R-LINT-014 finding, got: "
        + repr([(field(f, "rule_id"), field(f, "severity")) for f in field(report, "findings")])
    )
    hard = report["hard_failures"] if isinstance(report, dict) else report.hard_failures
    assert hard >= 1


def test_single_glossary_does_not_trigger_r_lint_014(tmp_path):
    root = _build_corpus(tmp_path / "repo", second_glossary=False)

    report = spec_linter.lint(None, root)

    findings = field(report, "findings")
    assert not [f for f in findings if field(f, "rule_id") == "R-LINT-014"]


def test_cli_reports_r_lint_014_fail_and_exit_1(tmp_path, capsys):
    root = _build_corpus(tmp_path / "repo", second_glossary=True)

    code = spec_linter.main(["--format=json", f"--repo-root={root}"])

    out = capsys.readouterr().out
    assert code == 1
    doc = json.loads(out)
    assert any(
        f["rule_id"] == "R-LINT-014" and f["severity"] == "fail"
        for f in doc["findings"]
    )
    assert doc["summary"]["hard_failures"] >= 1