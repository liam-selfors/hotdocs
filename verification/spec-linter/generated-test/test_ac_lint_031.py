# hotdocs-criterion: sha256:d86ad935f775f171c2c638546ab3de26b81f7088b2aa5204dfe1871e2e36f97b
"""AC-LINT-031: a component with interface/cli.md is warned (R-LINT-031)
unless one of its requirements cites interface/cli.md and a criterion
covers that requirement."""

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
        "id: comp-" + slug + "\n"
        "title: " + slug.capitalize() + " Component\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "sealed: true\n"
        "source_path: legacy/" + slug + "/\n"
        "---\n"
        "\n"
        "# " + slug.capitalize() + "\n"
        "\n"
        "## Purpose\n"
        "\n"
        "A fixture component used to test the CLI traceability rule.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: a tiny CLI.\n"
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


CLI_MD = (
    "# CLI\n"
    "\n"
    "```\n"
    "tool run [--format=json|text]\n"
    "```\n"
    "\n"
    "Exit codes: `0` success, `1` failure, `2` usage error.\n"
)


def citing_requirement(rid):
    return (
        "# " + rid + "\n"
        "\n"
        "**" + rid + "** — The command line described in `interface/cli.md`\n"
        "MUST accept `--format=value` and `--format value`; `--format` given\n"
        "with no value, an unknown argument, or a wrong subcommand MUST exit\n"
        "`2`; `--format` passes through to the library call; exit codes are\n"
        "`0`, `1` and `2` as listed there.\n"
    )


def plain_requirement(rid):
    return (
        "# " + rid + "\n"
        "\n"
        "**" + rid + "** — The component MUST return the sum of its two\n"
        "integer inputs.\n"
    )


def criterion(acid, rid):
    return (
        "# " + acid + "\n"
        "\n"
        "Covers: " + rid + "\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given the inputs 2 and 3\n"
        "When the component runs\n"
        "Then the result is 5\n"
        "```\n"
    )


CONSTRAINTS_MD = (
    "# Constraints\n"
    "\n"
    "- Runs in under one second, measured by timing one call.\n"
)


def build_component(repo_root, slug, requirement_text, with_criterion):
    up = slug.upper()
    base = repo_root / "specs" / "components" / slug
    rid = "R-" + up + "-001"
    write(base / "component.md", component_md(slug))
    write(base / "interface" / "cli.md", CLI_MD)
    write(base / "requirements" / (rid + ".md"), requirement_text(rid))
    if with_criterion:
        acid = "AC-" + up + "-001"
        write(base / "acceptance" / (acid + ".md"), criterion(acid, rid))
    write(base / "constraints.md", CONSTRAINTS_MD)


def finding_is_for(finding, slug):
    message = field(finding, "message") or ""
    file = str(field(finding, "file") or "").replace("\\", "/")
    comp_id = "comp-" + slug
    in_message = any(
        message[i:i + len(comp_id)] == comp_id
        and (i + len(comp_id) == len(message)
             or not (message[i + len(comp_id)].isalnum()
                     or message[i + len(comp_id)] == "-"))
        for i in range(len(message))
    )
    in_file = ("specs/components/" + slug + "/") in file
    return in_message or in_file


def test_ac_lint_031_cli_traceability_warns_only_uncovered(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Widget** — a fixture term.\n",
    )

    # 1: citing requirement, covered by a criterion -> no finding
    build_component(repo_root, "alpha", citing_requirement, True)
    # 2: citing requirement, no covering criterion -> warn
    build_component(repo_root, "beta", citing_requirement, False)
    # 3: no citing requirement at all -> warn
    build_component(repo_root, "gamma", plain_requirement, True)

    report = spec_linter.lint(None, repo_root)
    findings = list(field(report, "findings"))
    cli_findings = [f for f in findings if field(f, "rule_id") == "R-LINT-031"]

    alpha = [f for f in cli_findings if finding_is_for(f, "alpha")]
    beta = [f for f in cli_findings if finding_is_for(f, "beta")]
    gamma = [f for f in cli_findings if finding_is_for(f, "gamma")]

    assert alpha == [], "unexpected R-LINT-031 finding for comp-alpha: " + repr(alpha)
    assert len(beta) >= 1, "missing R-LINT-031 finding for comp-beta: " + repr(cli_findings)
    assert len(gamma) >= 1, "missing R-LINT-031 finding for comp-gamma: " + repr(cli_findings)

    # Only the second and third components get a finding.
    for f in cli_findings:
        assert finding_is_for(f, "beta") or finding_is_for(f, "gamma"), (
            "R-LINT-031 finding for an unexpected component: " + repr(f)
        )

    for f in beta + gamma:
        assert field(f, "severity") == "warn", repr(f)