# hotdocs-criterion: sha256:4457a902a8b939a7d2fd903318d1534b576e54f249d22a248c84b9f7bac5583a
"""AC-LINT-011: a Definitions entry that near-verbatim restates a glossary
term's definition is a fail-severity finding for rule R-LINT-011."""

from pathlib import Path

import spec_linter


GLOSSARY_TERM = "Blast radius"

GLOSSARY_DEFINITION = (
    "the minimal set of components the impact analyzer determines need "
    "regeneration or re-verification for a given spec change."
)

# One token changed out of ~17 distinct tokens: overlap well above 0.8.
NEAR_VERBATIM_DEFINITION = (
    "the minimal set of components the impact analyzer determines need "
    "regeneration or re-verification for a single spec change."
)

# A genuine delta: almost no token overlap with the glossary text.
DISTINCT_DEFINITION = (
    "within this linter, only downstream callers consuming its parsed "
    "JSON report output, counted per invocation."
)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_fixture(repo_root, local_definition):
    specs = repo_root / "specs"

    _write(
        specs / "glossary.md",
        "# Glossary\n"
        "\n"
        "Canonical vocabulary for this spec corpus.\n"
        "\n"
        "- **" + GLOSSARY_TERM + "** \u2014 " + GLOSSARY_DEFINITION + "\n"
        "- **Gate** \u2014 one verification step in the pipeline.\n",
    )

    comp = specs / "components" / "foo"
    _write(
        comp / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "sealed: true\n"
        "source_path: legacy/foo/\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Foo reports which components a change touches.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: reporting.\n"
        "- Out of scope: everything else.\n"
        "\n"
        "## Definitions\n"
        "\n"
        "- **" + GLOSSARY_TERM + "** \u2014 " + local_definition + "\n"
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
        "# R-FOO-001\n"
        "\n"
        "**R-FOO-001** \u2014 Foo MUST report every touched component.\n",
    )
    _write(
        comp / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n"
        "\n"
        "Covers: R-FOO-001\n"
        "Kind: compiled\n"
        "\n"
        "```gherkin\n"
        "Given a change to one component\n"
        "When foo runs\n"
        "Then the report names that component\n"
        "```\n",
    )
    _write(
        comp / "constraints.md",
        "# Constraints\n"
        "\n"
        "- Runs in under one second, measured by wall clock.\n",
    )


def _lint011_fails(report):
    return [
        f
        for f in field(report, "findings")
        if field(f, "rule_id") == "R-LINT-011" and field(f, "severity") == "fail"
    ]


def test_verbatim_copy_of_glossary_definition_fails_r_lint_011(tmp_path):
    repo_root = Path(tmp_path)
    _build_fixture(repo_root, GLOSSARY_DEFINITION)

    report = spec_linter.lint(None, repo_root)

    fails = _lint011_fails(report)
    assert fails, "expected a fail-severity R-LINT-011 finding, got: " + repr(
        field(report, "findings")
    )
    assert field(report, "hard_failures") >= 1


def test_near_verbatim_copy_of_glossary_definition_fails_r_lint_011(tmp_path):
    repo_root = Path(tmp_path)
    _build_fixture(repo_root, NEAR_VERBATIM_DEFINITION)

    report = spec_linter.lint(None, repo_root)

    fails = _lint011_fails(report)
    assert fails, "expected a fail-severity R-LINT-011 finding, got: " + repr(
        field(report, "findings")
    )
    assert field(report, "hard_failures") >= 1


def test_genuine_delta_does_not_fail_r_lint_011(tmp_path):
    repo_root = Path(tmp_path)
    _build_fixture(repo_root, DISTINCT_DEFINITION)

    report = spec_linter.lint(None, repo_root)

    assert _lint011_fails(report) == [], (
        "a dissimilar Definitions entry must not trigger R-LINT-011: "
        + repr(field(report, "findings"))
    )