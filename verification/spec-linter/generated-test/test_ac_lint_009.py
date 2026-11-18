# hotdocs-criterion: sha256:9eb73aaca947daba2323f06174ec579b181b848512cdfdf9547072a022128bbd
import json
from pathlib import Path

import pytest

import spec_linter


def _get(value, key, default=None):
    if isinstance(value, dict):
        return value.get(key, default)
    return getattr(value, key, default)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


COMPONENT_MD = """---
id: comp-foo
title: Foo
status: draft
owners: [alice]
sealed: true
source_path: legacy/foo
---

# Foo

## Purpose

Foo does one small thing for testing purposes.

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

REQ_MD = """# R-FOO-001

**R-FOO-001** — The component MUST return the one small thing.
"""

GOOD_AC_MD = """# AC-FOO-001

Covers: R-FOO-001
Kind: compiled

```gherkin
Given a request
When foo runs
Then it returns the one small thing
```
"""

CONSTRAINTS_MD = """# Constraints

None.
"""

GLOSSARY_MD = """# Glossary

- **Foo thing** — the one small thing foo returns.
"""


def _bad_ac(ac_id: str, target: str) -> str:
    return f"""# {ac_id}

Covers: {target}
Kind: compiled

```gherkin
Given a request
When foo runs
Then something happens
```
"""


def _build_fixture(root: Path, extra_acs=None) -> Path:
    comp = root / "specs" / "components" / "foo"
    _write(comp / "component.md", COMPONENT_MD)
    _write(comp / "requirements" / "R-FOO-001.md", REQ_MD)
    _write(comp / "acceptance" / "AC-FOO-001.md", GOOD_AC_MD)
    _write(comp / "constraints.md", CONSTRAINTS_MD)
    _write(root / "specs" / "glossary.md", GLOSSARY_MD)
    for ac_id, target in (extra_acs or []):
        _write(comp / "acceptance" / f"{ac_id}.md", _bad_ac(ac_id, target))
    return root


def _findings(report):
    findings = _get(report, "findings")
    if findings is None:
        findings = []
    return list(findings)


def _lint009_fails(report):
    return [
        f
        for f in _findings(report)
        if _get(f, "rule_id") == "R-LINT-009" and _get(f, "severity") == "fail"
    ]


def test_valid_covers_tag_produces_no_r_lint_009_finding(tmp_path):
    root = _build_fixture(tmp_path)
    report = spec_linter.lint(None, root)
    lint009 = [f for f in _findings(report) if _get(f, "rule_id") == "R-LINT-009"]
    assert lint009 == [], f"unexpected R-LINT-009 findings on clean fixture: {lint009}"


def test_dangling_r_id_covers_tag_is_fail_severity_r_lint_009(tmp_path):
    root = _build_fixture(tmp_path)
    baseline = spec_linter.lint(None, root)
    assert _lint009_fails(baseline) == []

    _write(
        root / "specs" / "components" / "foo" / "acceptance" / "AC-FOO-002.md",
        _bad_ac("AC-FOO-002", "R-DOES-NOT-EXIST"),
    )
    report = spec_linter.lint(None, root)
    fails = _lint009_fails(report)
    assert fails, (
        "expected a fail-severity R-LINT-009 finding for Covers: R-DOES-NOT-EXIST; "
        f"got findings: {_findings(report)}"
    )
    files = [str(_get(f, "file") or "") for f in fails]
    assert any("AC-FOO-002" in fp for fp in files), (
        f"R-LINT-009 finding should point at the offending criterion file; got {files}"
    )
    assert not any("AC-FOO-001" in fp for fp in files), (
        f"the valid criterion must not be flagged; got {files}"
    )

    hard = _get(report, "hard_failures")
    if hard is not None:
        assert hard >= 1


def test_dangling_p_id_covers_tag_is_fail_severity_r_lint_009(tmp_path):
    root = _build_fixture(tmp_path, extra_acs=[("AC-FOO-002", "P-DOES-NOT-EXIST")])
    report = spec_linter.lint(None, root)
    fails = _lint009_fails(report)
    assert fails, (
        "expected a fail-severity R-LINT-009 finding for Covers: P-DOES-NOT-EXIST; "
        f"got findings: {_findings(report)}"
    )


def test_cli_reports_r_lint_009_and_exits_1(tmp_path, capsys):
    root = _build_fixture(tmp_path, extra_acs=[("AC-FOO-002", "R-DOES-NOT-EXIST")])
    rc = spec_linter.main(["--format=json", f"--repo-root={root}"])
    out = capsys.readouterr().out
    assert rc == 1, f"expected exit code 1 with a fail-severity finding, got {rc}"
    data = json.loads(out)
    findings = data.get("findings", []) if isinstance(data, dict) else []
    assert any(
        f.get("rule_id") == "R-LINT-009" and f.get("severity") == "fail"
        for f in findings
    ), f"JSON report lacks a fail-severity R-LINT-009 finding: {findings}"