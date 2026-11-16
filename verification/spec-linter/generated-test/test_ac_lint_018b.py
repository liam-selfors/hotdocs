"""AC-LINT-018b (Covers: R-LINT-018).

Given a component's depends_on_guarantees lists G-DOES-NOT-EXIST
When hotdocs lint runs against it
Then the report contains a fail-severity finding for rule R-LINT-018
"""

from pathlib import Path

import spec_linter


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


COMPONENT_BODY = """
# Foo

## Purpose

Foo is a small synthetic component used only to exercise the spec linter's
guarantee-reference resolution in an isolated test corpus.

## Scope

- In scope: being linted.
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


def _build_corpus(repo_root: Path, guarantees_line: str) -> None:
    specs = repo_root / "specs"
    _write(
        specs / "glossary.md",
        "# Glossary\n\n- **Foo** — a synthetic test component.\n",
    )
    comp = specs / "components" / "foo"
    frontmatter = (
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "sealed: true\n"
        "source_path: legacy/foo/\n"
        f"{guarantees_line}"
        "---\n"
    )
    _write(comp / "component.md", frontmatter + COMPONENT_BODY)
    _write(
        comp / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n\n**R-FOO-001** — Foo MUST match existing behavior.\n",
    )
    _write(
        comp / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n\n"
        "Covers: R-FOO-001\n"
        "Kind: compiled\n\n"
        "```gherkin\n"
        "Given foo exists\n"
        "When foo runs\n"
        "Then foo matches existing behavior\n"
        "```\n",
    )
    _write(
        comp / "constraints.md",
        "# Constraints\n\n- None beyond existing behavior. Measured by: n/a.\n",
    )


def _findings(report):
    return list(field(report, "findings"))


def _r018_fail_findings(report):
    out = []
    for f in _findings(report):
        if field(f, "rule_id") == "R-LINT-018" and field(f, "severity") == "fail":
            out.append(f)
    return out


def test_baseline_without_bad_guarantee_has_no_r_lint_018_finding(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_corpus(repo_root, guarantees_line="")

    report = spec_linter.lint(None, repo_root)

    r018 = [f for f in _findings(report) if field(f, "rule_id") == "R-LINT-018"]
    assert r018 == [], f"unexpected R-LINT-018 findings in clean fixture: {r018!r}"


def test_unresolved_depends_on_guarantees_entry_is_fail_finding(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_corpus(
        repo_root, guarantees_line="depends_on_guarantees: [G-DOES-NOT-EXIST]\n"
    )

    report = spec_linter.lint(None, repo_root)

    fails = _r018_fail_findings(report)
    assert fails, (
        "expected a fail-severity R-LINT-018 finding for unresolved "
        f"G-DOES-NOT-EXIST; got findings: {_findings(report)!r}"
    )

    hard = field(report, "hard_failures")
    assert hard >= 1