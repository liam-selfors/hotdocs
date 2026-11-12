"""AC-LINT-018b (covers R-LINT-018).

Given a component's depends_on_guarantees lists G-DOES-NOT-EXIST
When hotdocs lint runs against it
Then the report contains a fail-severity finding for rule R-LINT-018
"""

import json
from pathlib import Path

import pytest

import spec_linter


def _field(value, name):
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def _findings(report):
    found = _field(report, "findings")
    return list(found or [])


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _component_md(extra_frontmatter: str = "") -> str:
    return (
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [alice]\n"
        "sealed: true\n"
        "source_path: legacy/foo\n"
        f"{extra_frontmatter}"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Foo does one small thing for testing the linter.\n"
        "\n"
        "## Rationale\n"
        "\n"
        "Exists only as a synthetic fixture.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: one small thing.\n"
        "- Out of scope: everything else.\n"
        "\n"
        "## Definitions\n"
        "\n"
        "None.\n"
        "\n"
        "## Behavior\n"
        "\n"
        "See `requirements/`.\n"
        "\n"
        "## Interfaces\n"
        "\n"
        "See `interface/`.\n"
        "\n"
        "## Data\n"
        "\n"
        "See `interface/data/`.\n"
        "\n"
        "## Acceptance criteria\n"
        "\n"
        "See `acceptance/`.\n"
        "\n"
        "## Non-functional constraints\n"
        "\n"
        "See `constraints.md`.\n"
        "\n"
        "## Open questions\n"
        "\n"
        "## Change log\n"
        "\n"
        "- Initial draft.\n"
    )


def _build_corpus(root: Path, extra_frontmatter: str = "") -> Path:
    comp = root / "specs" / "components" / "foo"
    _write(comp / "component.md", _component_md(extra_frontmatter))
    _write(
        comp / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n\n**R-FOO-001** — Foo MUST do one small thing.\n",
    )
    _write(
        comp / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n\n"
        "Covers: R-FOO-001\n"
        "Kind: compiled\n\n"
        "```gherkin\n"
        "Given foo is ready\n"
        "When foo runs\n"
        "Then foo does one small thing\n"
        "```\n",
    )
    _write(
        comp / "constraints.md",
        "# Constraints\n\nNone beyond the defaults.\n",
    )
    _write(
        root / "specs" / "glossary.md",
        "# Glossary\n\n- **Foo** — a synthetic fixture component.\n",
    )
    return root


def _r018_fails(findings):
    return [
        f
        for f in findings
        if _field(f, "rule_id") == "R-LINT-018" and _field(f, "severity") == "fail"
    ]


def test_baseline_without_depends_on_guarantees_has_no_r_lint_018(tmp_path):
    root = _build_corpus(tmp_path / "repo")
    report = spec_linter.lint(None, root)
    r018 = [f for f in _findings(report) if _field(f, "rule_id") == "R-LINT-018"]
    assert r018 == [], f"unexpected R-LINT-018 findings on clean fixture: {r018!r}"


def test_unresolvable_guarantee_yields_fail_finding_for_r_lint_018(tmp_path):
    root = _build_corpus(
        tmp_path / "repo",
        extra_frontmatter="depends_on_guarantees: [G-DOES-NOT-EXIST]\n",
    )
    report = spec_linter.lint(None, root)
    findings = _findings(report)
    matches = _r018_fails(findings)
    assert matches, (
        "expected a fail-severity R-LINT-018 finding for G-DOES-NOT-EXIST; got "
        f"{[(_field(f, 'rule_id'), _field(f, 'severity'), _field(f, 'message')) for f in findings]!r}"
    )

    hard_failures = _field(report, "hard_failures")
    if hard_failures is None:
        summary = _field(report, "summary")
        if summary is not None:
            hard_failures = _field(summary, "hard_failures")
    if hard_failures is not None:
        assert hard_failures >= 1


def test_unresolvable_guarantee_reported_via_cli_json(tmp_path, capsys):
    root = _build_corpus(
        tmp_path / "repo",
        extra_frontmatter="depends_on_guarantees: [G-DOES-NOT-EXIST]\n",
    )
    capsys.readouterr()
    code = spec_linter.main(["--format=json", f"--repo-root={root}"])
    out = capsys.readouterr().out
    assert code == 1, f"expected exit code 1 with a fail finding, got {code}"
    data = json.loads(out)
    findings = data.get("findings", []) if isinstance(data, dict) else []
    assert _r018_fails(findings), (
        f"CLI JSON report lacks a fail-severity R-LINT-018 finding: {out}"
    )