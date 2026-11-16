"""AC-LINT-019: a spec line ending in two trailing spaces yields a
fail-severity R-LINT-019 finding naming that line."""

import json
from pathlib import Path

import spec_linter


TARGET_REL = "specs/components/foo/requirements/R-FOO-001.md"
TARGET_LINE = 3


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _sev(value):
    sev = field(value, "severity")
    return getattr(sev, "value", sev)


def _norm(path_value):
    return Path(str(path_value)).as_posix()


COMPONENT_MD = """---
id: comp-foo
title: Foo
status: draft
owners: [team]
sealed: true
source_path: legacy/foo/
---

# Foo

## Purpose

Foo returns zero and prints nothing, for fixture purposes only.

## Scope

- In scope: returning zero.
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

CONSTRAINTS_MD = """# Constraints

None beyond the defaults.
"""

ACCEPTANCE_MD = """# AC-FOO-001

Covers: R-FOO-001
Kind: generated-test

```gherkin
Given the foo tool
When it runs
Then it returns zero
```
"""

GLOSSARY_MD = """# Glossary

- **Foo** — a fixture-only term.
"""


def _requirement(trailing: bool) -> str:
    third = "**R-FOO-001** — The foo tool MUST return zero."
    if trailing:
        third += "  "
    lines = [
        "# R-FOO-001",
        "",
        third,
        "It MUST NOT print anything.",
        "",
        "Rationale: fixture only.",
    ]
    return "\n".join(lines) + "\n"


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))


def _build_repo(root: Path, trailing: bool) -> Path:
    comp = root / "specs" / "components" / "foo"
    _write(comp / "component.md", COMPONENT_MD)
    _write(comp / "constraints.md", CONSTRAINTS_MD)
    _write(comp / "requirements" / "R-FOO-001.md", _requirement(trailing))
    _write(comp / "acceptance" / "AC-FOO-001.md", ACCEPTANCE_MD)
    _write(root / "specs" / "glossary.md", GLOSSARY_MD)
    return root


def _lint019(findings):
    return [f for f in findings if field(f, "rule_id") == "R-LINT-019"]


def test_clean_fixture_has_no_trailing_whitespace_finding(tmp_path):
    repo = _build_repo(tmp_path / "clean", trailing=False)
    report = spec_linter.lint(None, repo)
    assert _lint019(field(report, "findings")) == []


def test_trailing_spaces_reported_as_fail_on_that_line(tmp_path):
    repo = _build_repo(tmp_path / "dirty", trailing=True)
    # sanity: the fixture really has exactly that one trailing-space line
    raw_lines = (repo / TARGET_REL).read_text(encoding="utf-8").split("\n")
    assert raw_lines[TARGET_LINE - 1].endswith("  ")
    assert [i + 1 for i, l in enumerate(raw_lines) if l != l.rstrip()] == [
        TARGET_LINE
    ]

    report = spec_linter.lint(None, repo)
    hits = _lint019(field(report, "findings"))
    assert len(hits) == 1, hits
    hit = hits[0]
    assert _sev(hit) == "fail"
    assert _norm(field(hit, "file")) == TARGET_REL
    assert field(hit, "line") == TARGET_LINE

    hard = report["hard_failures"] if isinstance(report, dict) else report.hard_failures
    assert hard >= 1


def test_cli_reports_trailing_whitespace_and_exits_1(tmp_path, capsys):
    repo = _build_repo(tmp_path / "cli", trailing=True)
    capsys.readouterr()
    code = spec_linter.main([f"--repo-root={repo}", "--format=json"])
    out = capsys.readouterr().out
    assert code == 1
    doc = json.loads(out)
    hits = [f for f in doc["findings"] if f["rule_id"] == "R-LINT-019"]
    assert len(hits) == 1, hits
    assert hits[0]["severity"] == "fail"
    assert _norm(hits[0]["file"]) == TARGET_REL
    assert hits[0]["line"] == TARGET_LINE