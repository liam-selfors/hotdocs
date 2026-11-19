# hotdocs-criterion: sha256:64eba2eeba5325607c2e47f3b215a9fc4bd156ba5b225a9216b611f46af7d964
"""AC-LINT-018b: a depends_on_guarantees entry that does not resolve to an
existing G-<comp>-NNN id produces a fail-severity R-LINT-018 finding."""

from pathlib import Path

import spec_linter


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_fixture(repo_root):
    specs = repo_root / "specs"

    _write(
        specs / "glossary.md",
        "# Glossary\n"
        "\n"
        "- **Widget** \u2014 a thing the fixture component handles.\n",
    )

    comp_dir = specs / "components" / "foo"
    _write(
        comp_dir / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [fixture-team]\n"
        "sealed: true\n"
        "source_path: legacy/foo/\n"
        "depends_on_guarantees: [G-DOES-NOT-EXIST]\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Foo handles widgets for the fixture corpus.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: widgets.\n"
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
        comp_dir / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n"
        "\n"
        "**R-FOO-001** \u2014 Foo MUST match existing behavior.\n",
    )
    _write(
        comp_dir / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n"
        "\n"
        "Covers: R-FOO-001\n"
        "Kind: compiled\n"
        "\n"
        "```gherkin\n"
        "Given a widget\n"
        "When foo runs\n"
        "Then it matches existing behavior\n"
        "```\n",
    )
    _write(
        comp_dir / "constraints.md",
        "# Constraints\n"
        "\n"
        "None.\n",
    )


def test_unresolved_depends_on_guarantees_entry_fails_r_lint_018(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root)

    report = spec_linter.lint(None, repo_root)

    findings = list(field(report, "findings"))
    matching = [
        f
        for f in findings
        if field(f, "rule_id") == "R-LINT-018" and field(f, "severity") == "fail"
    ]
    assert matching, (
        "expected a fail-severity R-LINT-018 finding, got: "
        + repr(
            [
                (field(f, "rule_id"), field(f, "severity"), field(f, "message"))
                for f in findings
            ]
        )
    )
    assert field(report, "hard_failures") >= 1