# hotdocs-criterion: sha256:f30fe440434d1920aa5442f0511f5561378e5aa04069d3bb390663d1a32d3a10
"""AC-LINT-031: a component with interface/cli.md warns (R-LINT-031) unless one
of its requirements cites interface/cli.md and a criterion covers that
requirement."""

from pathlib import Path

import spec_linter


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def component_md(slug):
    return (
        "---\n"
        + "id: comp-" + slug + "\n"
        + "title: " + slug.capitalize() + " Component\n"
        + "status: draft\n"
        + "owners: [test-team]\n"
        + "sealed: true\n"
        + "source_path: legacy/" + slug + "/\n"
        + "---\n"
        + "\n"
        + "# " + slug.capitalize() + "\n"
        + "\n"
        + "## Purpose\n\n"
        + "A small fixture component used to exercise the linter.\n\n"
        + "## Scope\n\n"
        + "- In scope: fixture behavior.\n"
        + "- Out of scope: everything else.\n\n"
        + "## Definitions\n\nNone.\n\n"
        + "## Behavior\n\nSee `requirements/`.\n\n"
        + "## Interfaces\n\nSee `interface/`.\n\n"
        + "## Data\n\nSee `interface/data/`.\n\n"
        + "## Acceptance criteria\n\nSee `acceptance/`.\n\n"
        + "## Non-functional constraints\n\nSee `constraints.md`.\n\n"
        + "## Open questions\n\n"
        + "## Change log\n\n- Initial draft.\n"
    )


def cli_md(slug):
    return (
        "# CLI\n"
        + "\n"
        + "```\n"
        + "hotdocs " + slug + " [--format=json|text]\n"
        + "```\n"
        + "\n"
        + "Exit codes: `0` success, `2` usage error.\n"
    )


def citing_requirement(rid):
    return (
        "# " + rid + "\n"
        + "\n"
        + "**" + rid + "** — The command described in `interface/cli.md` MUST\n"
        + "accept `--format=value` and `--format value`, MUST treat a missing\n"
        + "value or an unknown argument as a usage error returning exit code\n"
        + "`2`, and MUST return `0` on success.\n"
    )


def plain_requirement(rid):
    return (
        "# " + rid + "\n"
        + "\n"
        + "**" + rid + "** — The component MUST return the sum of its two\n"
        + "integer inputs.\n"
    )


def criterion(acid, rid):
    return (
        "# " + acid + "\n"
        + "\n"
        + "Covers: " + rid + "\n"
        + "Kind: generated-test\n"
        + "\n"
        + "```gherkin\n"
        + "Given a valid input\n"
        + "When the component runs\n"
        + "Then it succeeds\n"
        + "```\n"
    )


def constraints_md():
    return "# Constraints\n\n- None beyond the defaults.\n"


def build_fixture(repo_root):
    specs = repo_root / "specs"
    write(
        specs / "glossary.md",
        "# Glossary\n\n- **Fixture** — a synthetic corpus for tests.\n",
    )

    # alpha: requirement cites interface/cli.md, criterion covers it.
    alpha = specs / "components" / "alpha"
    write(alpha / "component.md", component_md("alpha"))
    write(alpha / "interface" / "cli.md", cli_md("alpha"))
    write(alpha / "requirements" / "R-ALPHA-001.md", citing_requirement("R-ALPHA-001"))
    write(alpha / "acceptance" / "AC-ALPHA-001.md", criterion("AC-ALPHA-001", "R-ALPHA-001"))
    write(alpha / "constraints.md", constraints_md())

    # beta: requirement cites interface/cli.md, but no criterion covers it.
    beta = specs / "components" / "beta"
    write(beta / "component.md", component_md("beta"))
    write(beta / "interface" / "cli.md", cli_md("beta"))
    write(beta / "requirements" / "R-BETA-001.md", citing_requirement("R-BETA-001"))
    write(beta / "constraints.md", constraints_md())

    # gamma: no requirement cites interface/cli.md.
    gamma = specs / "components" / "gamma"
    write(gamma / "component.md", component_md("gamma"))
    write(gamma / "interface" / "cli.md", cli_md("gamma"))
    write(gamma / "requirements" / "R-GAMMA-001.md", plain_requirement("R-GAMMA-001"))
    write(gamma / "acceptance" / "AC-GAMMA-001.md", criterion("AC-GAMMA-001", "R-GAMMA-001"))
    write(gamma / "constraints.md", constraints_md())


def finding_names_component(finding, slug):
    file_value = str(field(finding, "file") or "").replace("\\", "/")
    message = str(field(finding, "message") or "")
    in_file = ("specs/components/" + slug + "/") in file_value
    in_message = ("comp-" + slug) in message
    return in_file or in_message


def test_ac_lint_031_only_uncovered_cli_components_warn(tmp_path):
    repo_root = Path(tmp_path)
    build_fixture(repo_root)

    report = spec_linter.lint(None, repo_root)
    findings = list(field(report, "findings"))
    cli_findings = [f for f in findings if field(f, "rule_id") == "R-LINT-031"]

    alpha = [f for f in cli_findings if finding_names_component(f, "alpha")]
    beta = [f for f in cli_findings if finding_names_component(f, "beta")]
    gamma = [f for f in cli_findings if finding_names_component(f, "gamma")]

    assert alpha == [], "covered CLI component must not get R-LINT-031: " + repr(alpha)
    assert len(beta) >= 1, "uncovered citing requirement must warn: " + repr(cli_findings)
    assert len(gamma) >= 1, "no citing requirement must warn: " + repr(cli_findings)

    # Every R-LINT-031 finding belongs to beta or gamma only.
    for f in cli_findings:
        assert finding_names_component(f, "beta") or finding_names_component(f, "gamma"), repr(f)

    for f in beta + gamma:
        assert field(f, "severity") == "warn", repr(f)

    # The finding names the component id.
    assert any("comp-beta" in str(field(f, "message")) for f in beta), repr(beta)
    assert any("comp-gamma" in str(field(f, "message")) for f in gamma), repr(gamma)