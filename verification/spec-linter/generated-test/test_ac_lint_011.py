# hotdocs-criterion: sha256:9ec34baac2dbe1aae70d1ea9e7c4bbf9818d85925543b3cc8bf3372018277f9d
"""AC-LINT-011: a Definitions entry that near-verbatim restates a glossary
term's definition (token-overlap ratio >= 0.8) is a fail-severity finding
for rule R-LINT-011."""

from pathlib import Path

import spec_linter


TERM = "Frobnication window"

GLOSSARY_DEFINITION = (
    "the bounded interval during which a widget accepts incoming "
    "frobnication requests from its upstream scheduler before it closes "
    "and rejects every later request outright."
)

# Near-verbatim copy: one word changed ("outright" -> "immediately"),
# far above a 0.8 token-overlap ratio under any reasonable normalization.
NEAR_VERBATIM_LOCAL = (
    "the bounded interval during which a widget accepts incoming "
    "frobnication requests from its upstream scheduler before it closes "
    "and rejects every later request immediately."
)

# A genuine delta: shares almost no tokens with the glossary definition.
GENUINE_DELTA_LOCAL = (
    "in this component, measured in milliseconds; zero disables "
    "batching entirely."
)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_corpus(repo_root, local_definition):
    specs = repo_root / "specs"

    write(
        specs / "glossary.md",
        "# Glossary\n"
        "\n"
        "Canonical vocabulary for this fixture corpus.\n"
        "\n"
        "- **" + TERM + "** \u2014 " + GLOSSARY_DEFINITION + "\n"
        "- **Widget** \u2014 a unit of fixture behavior used only in tests.\n",
    )

    comp = specs / "components" / "widget"
    write(
        comp / "component.md",
        "---\n"
        "id: comp-widget\n"
        "title: Widget\n"
        "status: draft\n"
        "owners: [fixture-team]\n"
        "sealed: true\n"
        "source_path: legacy/widget/\n"
        "---\n"
        "\n"
        "# Widget\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Accepts frobnication requests for the fixture corpus.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: accepting requests.\n"
        "- Out of scope: everything else.\n"
        "\n"
        "## Definitions\n"
        "\n"
        "- **" + TERM + "** \u2014 " + local_definition + "\n"
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
        comp / "requirements" / "R-WIDGET-001.md",
        "# R-WIDGET-001\n"
        "\n"
        "**R-WIDGET-001** \u2014 The widget MUST accept a request while its "
        "frobnication window is open.\n",
    )
    write(
        comp / "acceptance" / "AC-WIDGET-001.md",
        "# AC-WIDGET-001\n"
        "\n"
        "Covers: R-WIDGET-001\n"
        "Kind: compiled\n"
        "\n"
        "```gherkin\n"
        "Given an open frobnication window\n"
        "When a request arrives\n"
        "Then the widget accepts it\n"
        "```\n",
    )
    write(
        comp / "constraints.md",
        "# Constraints\n"
        "\n"
        "- None beyond the defaults.\n",
    )


def lint_findings(repo_root):
    report = spec_linter.lint(None, repo_root)
    return report, list(field(report, "findings"))


def r_lint_011_findings(findings):
    return [f for f in findings if field(f, "rule_id") == "R-LINT-011"]


def test_near_verbatim_glossary_restatement_fails_r_lint_011(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_corpus(repo_root, NEAR_VERBATIM_LOCAL)

    report, findings = lint_findings(repo_root)
    hits = r_lint_011_findings(findings)

    assert hits, (
        "expected an R-LINT-011 finding for a near-verbatim restatement; got "
        + repr([(field(f, "rule_id"), field(f, "severity"), field(f, "message")) for f in findings])
    )
    assert any(field(f, "severity") == "fail" for f in hits), repr(
        [(field(f, "severity"), field(f, "message")) for f in hits]
    )
    assert field(report, "hard_failures") >= 1


def test_genuine_delta_is_not_flagged_by_r_lint_011(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_corpus(repo_root, GENUINE_DELTA_LOCAL)

    _report, findings = lint_findings(repo_root)
    hits = [
        f for f in r_lint_011_findings(findings) if field(f, "severity") == "fail"
    ]

    assert hits == [], repr([(field(f, "file"), field(f, "message")) for f in hits])