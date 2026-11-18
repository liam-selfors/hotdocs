# hotdocs-criterion: sha256:1cd2506c2c779d3c7b8aab44f2696294f0a8ac59b0501a460f5a40a5d199163e
"""AC-LINT-014: two glossary-like files under specs/ with no architecture-level
bounded-context split decision produce a fail-severity R-LINT-014 finding."""

import json
from pathlib import Path

import spec_linter


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_corpus(repo_root):
    specs = repo_root / "specs"
    comp = specs / "components" / "foo"

    _write(
        comp / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "sealed: true\n"
        "source_path: legacy/foo/\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Foo matches existing behavior and is not regenerated.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: foo behavior.\n"
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
        "- Initial draft.\n",
    )
    _write(
        comp / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n\n**R-FOO-001** — Foo MUST match existing behavior.\n",
    )
    _write(
        comp / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n"
        "\n"
        "Covers: R-FOO-001\n"
        "Kind: compiled\n"
        "\n"
        "```gherkin\n"
        "Given an input\n"
        "When foo runs\n"
        "Then the output matches existing behavior\n"
        "```\n",
    )
    _write(
        comp / "constraints.md",
        "# Constraints\n\nNone beyond existing behavior.\n",
    )

    # Two files that both declare themselves a corpus glossary.
    _write(
        specs / "glossary.md",
        "# Glossary\n"
        "\n"
        "Canonical vocabulary for this spec corpus.\n"
        "\n"
        "- **Widget** — a unit of work handled by foo.\n",
    )
    _write(
        specs / "glossary-billing.md",
        "# Glossary\n"
        "\n"
        "Canonical vocabulary for this spec corpus (billing terms).\n"
        "\n"
        "- **Invoice** — a request for payment.\n",
    )
    # Deliberately no specs/architecture/ document recording a
    # bounded-context split decision.


def _r014_fails(findings):
    return [
        f
        for f in findings
        if field(f, "rule_id") == "R-LINT-014" and field(f, "severity") == "fail"
    ]


def test_two_glossaries_without_split_decision_fail_lint(tmp_path):
    repo_root = tmp_path / "repo"
    _build_corpus(repo_root)

    report = spec_linter.lint(None, repo_root)

    findings = list(field(report, "findings"))
    hits = _r014_fails(findings)
    assert hits, "expected a fail-severity R-LINT-014 finding, got: " + repr(
        [(field(f, "rule_id"), field(f, "severity"), field(f, "file")) for f in findings]
    )
    assert field(report, "hard_failures") >= 1


def test_two_glossaries_without_split_decision_fail_cli_json(tmp_path, capsys):
    repo_root = tmp_path / "repo"
    _build_corpus(repo_root)

    code = spec_linter.main(["--format=json", "--repo-root=" + str(repo_root)])
    out = capsys.readouterr().out

    assert code == 1
    doc = json.loads(out)
    hits = _r014_fails(doc["findings"])
    assert hits, "expected a fail-severity R-LINT-014 finding in JSON report"
    assert doc["summary"]["hard_failures"] >= 1