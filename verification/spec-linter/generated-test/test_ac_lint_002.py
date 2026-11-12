import json
from pathlib import Path

import spec_linter


def _get(value, name, default=None):
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _sev(value):
    sev = _get(value, "severity")
    if sev is None:
        return None
    sev_value = getattr(sev, "value", sev)
    return str(sev_value)


def _norm(path_value):
    if path_value is None:
        return ""
    return str(path_value).replace("\\", "/")


COMPONENT_TEMPLATE = """---
id: comp-foo
title: Foo
status: ratified
owners: [alice]
sealed: true
source_path: legacy/foo
last_ratified_commit: 0123456789abcdef0123456789abcdef01234567
---

# Foo

## Purpose

Foo does a small, well-defined thing for testing.

## Scope

- In scope: the small thing.
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
{open_questions}
## Change log

- Initial draft.
"""


def _build_repo(root: Path, open_questions: str) -> Path:
    specs = root / "specs"
    comp = specs / "components" / "foo"
    (comp / "requirements").mkdir(parents=True)
    (comp / "acceptance").mkdir(parents=True)
    (comp / "interface").mkdir(parents=True)

    (specs / "glossary.md").write_text(
        "# Glossary\n\n- **Foo thing** — a thing used only in tests.\n",
        encoding="utf-8",
    )

    component_md = comp / "component.md"
    component_md.write_text(
        COMPONENT_TEMPLATE.format(open_questions=open_questions),
        encoding="utf-8",
    )

    (comp / "requirements" / "R-FOO-001.md").write_text(
        "# R-FOO-001\n\n**R-FOO-001** — The component MUST do the small thing.\n",
        encoding="utf-8",
    )
    (comp / "acceptance" / "AC-FOO-001.md").write_text(
        "# AC-FOO-001\n\nCovers: R-FOO-001\nKind: compiled\n\n"
        "```gherkin\nGiven a small thing\nWhen foo runs\nThen the small thing is done\n```\n",
        encoding="utf-8",
    )
    (comp / "constraints.md").write_text(
        "# Constraints\n\n- None measurable beyond defaults.\n",
        encoding="utf-8",
    )
    return component_md


NON_EMPTY_OPEN_QUESTIONS = (
    "\n- Should foo also handle the large thing? Undecided.\n\n"
)
EMPTY_OPEN_QUESTIONS = "\n"


def _r_lint_002_fails_for_component(findings):
    hits = []
    for f in findings or []:
        if _get(f, "rule_id") != "R-LINT-002":
            continue
        if _sev(f) != "fail":
            continue
        hits.append(f)
    return hits


def _refers_to_component_md(finding):
    return _norm(_get(finding, "file")).endswith("components/foo/component.md")


def test_ratified_with_open_questions_reports_r_lint_002_fail(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_repo(repo_root, NON_EMPTY_OPEN_QUESTIONS)

    report = spec_linter.lint(None, repo_root)
    findings = _get(report, "findings")
    assert findings is not None, "LintReport must expose findings"

    hits = _r_lint_002_fails_for_component(findings)
    assert hits, (
        "expected a fail-severity R-LINT-002 finding, got: "
        + repr([(_get(f, "rule_id"), _sev(f), _get(f, "file")) for f in findings])
    )
    assert any(_refers_to_component_md(f) for f in hits), (
        "R-LINT-002 finding should be reported against the component.md: "
        + repr([_get(f, "file") for f in hits])
    )

    hard_failures = _get(report, "hard_failures")
    if hard_failures is None:
        summary = _get(report, "summary")
        if summary is not None:
            hard_failures = _get(summary, "hard_failures")
    if hard_failures is not None:
        assert hard_failures >= 1


def test_ratified_with_empty_open_questions_has_no_r_lint_002_for_open_questions(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_repo(repo_root, EMPTY_OPEN_QUESTIONS)

    report = spec_linter.lint(None, repo_root)
    findings = _get(report, "findings") or []

    hits = [
        f
        for f in _r_lint_002_fails_for_component(findings)
        if _refers_to_component_md(f)
    ]
    assert not hits, (
        "a ratified spec with an empty Open questions section and a "
        "last_ratified_commit must not fail R-LINT-002: "
        + repr([_get(f, "message") for f in hits])
    )


def test_cli_lint_reports_r_lint_002_fail_and_exits_1(tmp_path, capsys):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_repo(repo_root, NON_EMPTY_OPEN_QUESTIONS)

    capsys.readouterr()
    code = spec_linter.main(["--format=json", f"--repo-root={repo_root}"])
    out = capsys.readouterr().out

    assert code == 1, f"expected exit code 1 for a fail finding, got {code!r}"

    data = json.loads(out)
    findings = data.get("findings") if isinstance(data, dict) else None
    assert isinstance(findings, list), f"JSON output lacks findings list: {out!r}"

    hits = _r_lint_002_fails_for_component(findings)
    assert hits, f"expected R-LINT-002 fail finding in CLI JSON output: {out!r}"
    assert any(_refers_to_component_md(f) for f in hits)