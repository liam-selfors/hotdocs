# hotdocs-criterion: sha256:c92b0e4f57aecaf3f486084aae4fdd9f3a5d39aeb7131472f37b20ce5d77fe9a
"""AC-LINT-011b: a Definitions entry for a glossary term that adds genuinely
new, component-specific nuance (low textual overlap with the glossary's own
definition) is a permitted delta, so the lint report carries no R-LINT-011
finding."""

from pathlib import Path

import spec_linter


TERM = "Widget"

GLOSSARY_DEFINITION = (
    "reusable rendering unit composed into dashboard pages, "
    "refreshed every poll cycle."
)

# Shares no tokens with GLOSSARY_DEFINITION: genuinely new nuance.
LOCAL_DELTA = (
    "In this component, exclusively signed bundles qualify; unsigned "
    "artifacts stay quarantined pending operator approval."
)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_corpus(repo_root, local_definition):
    specs = repo_root / "specs"

    _write(
        specs / "glossary.md",
        "# Glossary\n"
        "\n"
        "Canonical vocabulary.\n"
        "\n"
        "- **" + TERM + "** \u2014 " + GLOSSARY_DEFINITION + "\n",
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
        "Foo validates incoming widgets before they are displayed.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: widget validation.\n"
        "- Out of scope: rendering.\n"
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
    _write(
        comp / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n"
        "\n"
        "**R-FOO-001** \u2014 Foo MUST reject an unsigned widget.\n",
    )
    _write(
        comp / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n"
        "\n"
        "Covers: R-FOO-001\n"
        "Kind: compiled\n"
        "\n"
        "```gherkin\n"
        "Given an unsigned widget\n"
        "When foo validates it\n"
        "Then it is rejected\n"
        "```\n",
    )
    _write(
        comp / "constraints.md",
        "# Constraints\n"
        "\n"
        "- Validation completes within 1 second, measured by a timer.\n",
    )


def _lint011_findings(repo_root):
    report = spec_linter.lint(None, repo_root)
    findings = field(report, "findings")
    return [f for f in findings if field(f, "rule_id") == "R-LINT-011"]


def test_low_overlap_definitions_delta_is_not_flagged(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_corpus(repo_root, LOCAL_DELTA)

    findings = _lint011_findings(repo_root)

    assert findings == [], (
        "a genuinely new, low-overlap Definitions delta must not be "
        "reported as an R-LINT-011 redefinition, got: " + repr(findings)
    )


def test_control_verbatim_restatement_is_flagged(tmp_path):
    # Sanity control: the same fixture shape with the glossary text restated
    # verbatim does trigger R-LINT-011, so the absence above is meaningful.
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_corpus(repo_root, GLOSSARY_DEFINITION)

    findings = _lint011_findings(repo_root)

    assert findings, "a verbatim restatement must produce an R-LINT-011 finding"
    for f in findings:
        assert field(f, "severity") == "fail"