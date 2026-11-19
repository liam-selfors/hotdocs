# hotdocs-criterion: sha256:1cd2506c2c779d3c7b8aab44f2696294f0a8ac59b0501a460f5a40a5d199163e
from pathlib import Path

import spec_linter


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_fixture(repo_root):
    specs = repo_root / "specs"
    comp = specs / "components" / "foo"

    write(
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
        "Foo does a small thing for the fixture.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: the small thing.\n"
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
    write(
        comp / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n\n**R-FOO-001** — Foo MUST match existing behavior.\n",
    )
    write(
        comp / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n"
        "\n"
        "Covers: R-FOO-001\n"
        "Kind: compiled\n"
        "\n"
        "```gherkin\n"
        "Given foo\n"
        "When it runs\n"
        "Then it matches existing behavior\n"
        "```\n",
    )
    write(
        comp / "constraints.md",
        "# Constraints\n\nNone.\n",
    )

    # Two files under specs/ that both declare themselves a corpus glossary.
    write(
        specs / "glossary.md",
        "# Glossary\n"
        "\n"
        "Canonical vocabulary for this spec corpus.\n"
        "\n"
        "- **Widget** — a small thing the fixture talks about.\n",
    )
    write(
        specs / "glossary-billing.md",
        "# Glossary\n"
        "\n"
        "Canonical vocabulary for this spec corpus's billing subsystem.\n"
        "\n"
        "- **Invoice** — a request for payment.\n",
    )
    # No specs/architecture/ document records a bounded-context split.


def test_two_glossaries_without_split_decision_fail_r_lint_014(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root)

    assert not (repo_root / "specs" / "architecture").exists()

    report = spec_linter.lint(None, repo_root)

    findings = list(field(report, "findings"))
    matching = [
        f
        for f in findings
        if field(f, "rule_id") == "R-LINT-014" and field(f, "severity") == "fail"
    ]
    assert matching, (
        "expected a fail-severity R-LINT-014 finding, got: "
        + repr(
            [
                (field(f, "rule_id"), field(f, "severity"), field(f, "file"), field(f, "message"))
                for f in findings
            ]
        )
    )
    assert field(report, "hard_failures") >= 1