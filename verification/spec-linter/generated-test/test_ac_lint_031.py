# hotdocs-criterion: sha256:1163af59f0ff8f110eff0d71dadaebbde6ab5972372c6d3b5741aedeb988b11c
from pathlib import Path

import spec_linter


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


SLUGS = ["alpha-tool", "beta-tool", "gamma-tool"]


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _component_md(slug, name):
    return (
        "---\n"
        + "id: comp-" + slug + "\n"
        + "title: " + name + "\n"
        + "status: draft\n"
        + "owners: [test-team]\n"
        + "depends_on: []\n"
        + "sealed: true\n"
        + "source_path: legacy/" + slug + "/\n"
        + "---\n"
        + "\n"
        + "# " + name + "\n"
        + "\n"
        + "## Purpose\n\nA small command-line tool used as a test fixture.\n\n"
        + "## Scope\n\n- In scope: its command line.\n- Out of scope: everything else.\n\n"
        + "## Definitions\n\nNone.\n\n"
        + "## Behavior\n\nSee `requirements/`.\n\n"
        + "## Interfaces\n\nSee `interface/`.\n\n"
        + "## Data\n\nSee `interface/data/`.\n\n"
        + "## Acceptance criteria\n\nSee `acceptance/`.\n\n"
        + "## Non-functional constraints\n\nSee `constraints.md`.\n\n"
        + "## Open questions\n\n"
        + "## Change log\n\n- Initial draft.\n"
    )


def _cli_md(slug):
    return (
        "# CLI\n\n```\n"
        + slug + " [--format=json|text]\n"
        + "```\n\nPrints a greeting.\n"
    )


def _citing_requirement(rid, slug):
    return (
        "# " + rid + "\n\n"
        + "**" + rid + "** — The command line documented in `interface/cli.md` "
        + "MUST accept `--format=json` and `--format json`, MUST treat `--format` "
        + "given with no value as a usage error, MUST reject an unknown argument "
        + "as a usage error, and MUST exit `0` on success and `2` on a usage error.\n"
    )


def _plain_requirement(rid):
    return (
        "# " + rid + "\n\n"
        + "**" + rid + "** — The tool MUST print the greeting `hello` when run.\n"
    )


def _acceptance(aid, rid):
    return (
        "# " + aid + "\n\n"
        + "Covers: " + rid + "\n"
        + "Kind: generated-test\n\n"
        + "```gherkin\n"
        + "Given the tool\n"
        + "When it runs\n"
        + "Then it behaves as " + rid + " states\n"
        + "```\n"
    )


def _build_corpus(repo_root):
    specs = repo_root / "specs"
    _write(specs / "glossary.md", "# Glossary\n\n- **Fixture** — a test corpus.\n")

    # Component 1: citing requirement, covered by a criterion.
    a = specs / "components" / "alpha-tool"
    _write(a / "component.md", _component_md("alpha-tool", "Alpha Tool"))
    _write(a / "interface" / "cli.md", _cli_md("alpha-tool"))
    _write(a / "requirements" / "R-ALPHA-001.md", _citing_requirement("R-ALPHA-001", "alpha-tool"))
    _write(a / "acceptance" / "AC-ALPHA-001.md", _acceptance("AC-ALPHA-001", "R-ALPHA-001"))
    _write(a / "constraints.md", "# Constraints\n\nNone.\n")

    # Component 2: citing requirement with no covering criterion.
    b = specs / "components" / "beta-tool"
    _write(b / "component.md", _component_md("beta-tool", "Beta Tool"))
    _write(b / "interface" / "cli.md", _cli_md("beta-tool"))
    _write(b / "requirements" / "R-BETA-001.md", _citing_requirement("R-BETA-001", "beta-tool"))
    _write(b / "requirements" / "R-BETA-002.md", _plain_requirement("R-BETA-002"))
    _write(b / "acceptance" / "AC-BETA-001.md", _acceptance("AC-BETA-001", "R-BETA-002"))
    _write(b / "constraints.md", "# Constraints\n\nNone.\n")

    # Component 3: no requirement cites interface/cli.md.
    c = specs / "components" / "gamma-tool"
    _write(c / "component.md", _component_md("gamma-tool", "Gamma Tool"))
    _write(c / "interface" / "cli.md", _cli_md("gamma-tool"))
    _write(c / "requirements" / "R-GAMMA-001.md", _plain_requirement("R-GAMMA-001"))
    _write(c / "acceptance" / "AC-GAMMA-001.md", _acceptance("AC-GAMMA-001", "R-GAMMA-001"))
    _write(c / "constraints.md", "# Constraints\n\nNone.\n")


def _owning_slug(finding):
    file_value = field(finding, "file")
    file_text = str(file_value).replace("\\", "/") if file_value is not None else ""
    message = str(field(finding, "message") or "")
    for slug in SLUGS:
        if "components/" + slug + "/" in file_text:
            return slug
    for slug in SLUGS:
        if "comp-" + slug in message:
            return slug
    return None


def test_r_lint_031_warns_only_for_uncovered_or_uncited_cli(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_corpus(repo_root)

    report = spec_linter.lint(None, repo_root)
    findings = list(field(report, "findings"))
    cli_findings = [f for f in findings if field(f, "rule_id") == "R-LINT-031"]

    by_slug = {}
    for f in cli_findings:
        slug = _owning_slug(f)
        assert slug is not None, "R-LINT-031 finding not attributable to a fixture component: " + repr(f)
        by_slug.setdefault(slug, []).append(f)

    assert set(by_slug) == {"beta-tool", "gamma-tool"}, repr(cli_findings)
    assert "alpha-tool" not in by_slug

    for slug in ("beta-tool", "gamma-tool"):
        assert len(by_slug[slug]) >= 1
        for f in by_slug[slug]:
            assert field(f, "severity") == "warn", repr(f)