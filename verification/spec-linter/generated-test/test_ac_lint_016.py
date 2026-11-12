import json
from pathlib import Path

import pytest

import spec_linter


def _get(value, name, default=None):
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


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

Foo does one small thing for the test fixture.

## Scope

- In scope: foo.
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

REQUIREMENT_BODY = """# R-FOO-001

**R-FOO-001** — The component MUST do foo.
"""

REQUIREMENT_WITH_FRONTMATTER = """---
id: R-FOO-001
title: Foo requirement
status: draft
---

""" + REQUIREMENT_BODY

ACCEPTANCE_MD = """# AC-FOO-001

Covers: R-FOO-001
Kind: generated-test

```gherkin
Given foo
When foo runs
Then foo happens
```
"""

CONSTRAINTS_MD = """# Constraints

- None beyond the defaults.
"""

GLOSSARY_MD = """# Glossary

- **Foo** — a test fixture term.
"""


def _build_corpus(root: Path, requirement_text: str) -> Path:
    comp = root / "specs" / "components" / "foo"
    _write(comp / "component.md", COMPONENT_MD)
    _write(comp / "requirements" / "R-FOO-001.md", requirement_text)
    _write(comp / "acceptance" / "AC-FOO-001.md", ACCEPTANCE_MD)
    _write(comp / "constraints.md", CONSTRAINTS_MD)
    _write(root / "specs" / "glossary.md", GLOSSARY_MD)
    return root


def _findings(report):
    findings = _get(report, "findings", None)
    assert findings is not None, "LintReport has no findings field"
    return list(findings)


def _norm(path_value) -> str:
    return str(path_value).replace("\\", "/")


def _r016_findings(findings):
    return [f for f in findings if _get(f, "rule_id") == "R-LINT-016"]


def test_requirement_file_with_frontmatter_fails_r_lint_016(tmp_path):
    root = _build_corpus(tmp_path / "repo", REQUIREMENT_WITH_FRONTMATTER)

    report = spec_linter.lint(None, root)
    findings = _findings(report)

    r016 = _r016_findings(findings)
    assert r016, (
        "expected an R-LINT-016 finding for frontmatter in a requirement unit "
        f"file; got rules {[_get(f, 'rule_id') for f in findings]}"
    )

    on_requirement = [
        f for f in r016
        if _norm(_get(f, "file", "")).endswith("requirements/R-FOO-001.md")
    ]
    assert on_requirement, (
        "expected the R-LINT-016 finding to name requirements/R-FOO-001.md; "
        f"got files {[_get(f, 'file') for f in r016]}"
    )
    assert any(_get(f, "severity") == "fail" for f in on_requirement), (
        "expected R-LINT-016 finding to have fail severity; got "
        f"{[_get(f, 'severity') for f in on_requirement]}"
    )

    hard_failures = _get(report, "hard_failures", None)
    if hard_failures is None:
        summary = _get(report, "summary", None)
        if summary is not None:
            hard_failures = _get(summary, "hard_failures", None)
    if hard_failures is not None:
        assert hard_failures >= 1


def test_component_md_frontmatter_and_clean_unit_files_not_flagged(tmp_path):
    root = _build_corpus(tmp_path / "repo", REQUIREMENT_BODY)

    report = spec_linter.lint(None, root)
    findings = _findings(report)

    r016 = _r016_findings(findings)
    assert not r016, (
        "no unit file carries frontmatter (only component.md does), so "
        f"R-LINT-016 must not fire; got {[(_get(f, 'file'), _get(f, 'message')) for f in r016]}"
    )


def test_cli_reports_r_lint_016_and_exits_1(tmp_path, capsys):
    root = _build_corpus(tmp_path / "repo", REQUIREMENT_WITH_FRONTMATTER)

    code = spec_linter.main(["--format=json", "--repo-root=" + str(root)])
    out = capsys.readouterr().out

    assert code == 1, f"expected exit code 1 for a fail-severity finding, got {code}"

    data = json.loads(out)
    findings = data.get("findings", []) if isinstance(data, dict) else []
    r016 = [
        f for f in findings
        if f.get("rule_id") == "R-LINT-016"
        and f.get("severity") == "fail"
        and _norm(f.get("file", "")).endswith("requirements/R-FOO-001.md")
    ]
    assert r016, f"expected a fail-severity R-LINT-016 finding in JSON output; got {findings}"