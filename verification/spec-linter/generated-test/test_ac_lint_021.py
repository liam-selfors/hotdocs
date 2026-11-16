import json
from pathlib import Path

import spec_linter


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


COMPONENT_TEMPLATE = """---
id: comp-{slug}
title: {title}
status: draft
owners: [team-test]
sealed: true
source_path: legacy/{slug}/
---

# {title}

## Purpose

The {slug} component is a small synthetic fixture used to exercise the linter's traceability checks.

## Scope

- In scope: a single synthetic behavior.
- Out of scope: everything else.

## Definitions

None beyond the glossary.

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

REQUIREMENT_TEMPLATE = """# {rid}

**{rid}** — The {slug} component MUST return the input value unchanged.
"""

ACCEPTANCE_TEMPLATE = """# {acid}

Covers: {covers}
Kind: generated-test

```gherkin
Given an input value
When the {slug} component processes it
Then the same value is returned
```
"""

CONSTRAINTS = """# Constraints

- Latency: under 1 second per call. Measurement: wall-clock timing in a unit test.
"""

GLOSSARY = """# Glossary

- **Fixture** — a synthetic spec used only for testing.
"""


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _make_component(specs: Path, slug: str, title: str) -> Path:
    root = specs / "components" / slug
    _write(root / "component.md", COMPONENT_TEMPLATE.format(slug=slug, title=title))
    _write(root / "constraints.md", CONSTRAINTS)
    (root / "interface").mkdir(parents=True, exist_ok=True)
    return root


def _build_fixture(repo_root: Path) -> None:
    specs = repo_root / "specs"
    for sub in ("product", "architecture", "vars", "decisions"):
        (specs / sub).mkdir(parents=True, exist_ok=True)
    _write(specs / "glossary.md", GLOSSARY)

    # comp-foo: R-FOO-001 with no acceptance criterion covering it.
    foo = _make_component(specs, "foo", "Foo")
    _write(
        foo / "requirements" / "R-FOO-001.md",
        REQUIREMENT_TEMPLATE.format(rid="R-FOO-001", slug="foo"),
    )
    (foo / "acceptance").mkdir(parents=True, exist_ok=True)

    # comp-bar: R-BAR-001 covered by AC-BAR-001; AC-BAR-002 covers a
    # nonexistent R-BAR-999.
    bar = _make_component(specs, "bar", "Bar")
    _write(
        bar / "requirements" / "R-BAR-001.md",
        REQUIREMENT_TEMPLATE.format(rid="R-BAR-001", slug="bar"),
    )
    _write(
        bar / "acceptance" / "AC-BAR-001.md",
        ACCEPTANCE_TEMPLATE.format(acid="AC-BAR-001", covers="R-BAR-001", slug="bar"),
    )
    _write(
        bar / "acceptance" / "AC-BAR-002.md",
        ACCEPTANCE_TEMPLATE.format(acid="AC-BAR-002", covers="R-BAR-999", slug="bar"),
    )


def _traceability_findings(findings):
    return [
        f
        for f in findings
        if field(f, "rule_id") in ("R-LINT-008", "R-LINT-009")
    ]


def _mentions(finding, token):
    text = "{} {}".format(field(finding, "file") or "", field(finding, "message") or "")
    return token in text


def _assert_exact_traceability(findings):
    trace = _traceability_findings(findings)
    assert len(trace) == 2, "expected exactly two R-LINT-008/009 findings, got: {!r}".format(
        [(field(f, "rule_id"), field(f, "file"), field(f, "message")) for f in trace]
    )

    r008 = [f for f in trace if field(f, "rule_id") == "R-LINT-008"]
    r009 = [f for f in trace if field(f, "rule_id") == "R-LINT-009"]
    assert len(r008) == 1, r008
    assert len(r009) == 1, r009

    f008 = r008[0]
    assert field(f008, "severity") == "fail"
    assert _mentions(f008, "R-FOO-001"), (field(f008, "file"), field(f008, "message"))
    assert not _mentions(f008, "R-BAR-001")

    f009 = r009[0]
    assert field(f009, "severity") == "fail"
    assert _mentions(f009, "AC-BAR-002"), (field(f009, "file"), field(f009, "message"))
    assert not _mentions(f009, "AC-BAR-001")


def test_ac_lint_021_traceability_findings_via_lint(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root)

    report = spec_linter.lint(None, repo_root)
    findings = report["findings"] if isinstance(report, dict) else report.findings

    _assert_exact_traceability(findings)

    hard = report["hard_failures"] if isinstance(report, dict) else report.hard_failures
    assert hard >= 2


def test_ac_lint_021_traceability_findings_via_cli_json(tmp_path, capsys):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root)

    code = spec_linter.main(["--format=json", "--repo-root", str(repo_root)])
    out = capsys.readouterr().out

    assert code == 1
    doc = json.loads(out)
    _assert_exact_traceability(doc["findings"])