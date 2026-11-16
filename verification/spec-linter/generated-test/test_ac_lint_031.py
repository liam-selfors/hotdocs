"""AC-LINT-031: a component with interface/cli.md gets an R-LINT-031 warn
finding unless one of its requirements cites `interface/cli.md` and a
criterion covers that requirement."""

import spec_linter


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _component_md(slug):
    return (
        "---\n"
        f"id: comp-{slug}\n"
        f"title: {slug.replace('-', ' ').title()}\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "sealed: true\n"
        f"source_path: legacy/{slug}/\n"
        "---\n"
        "\n"
        f"# {slug}\n"
        "\n"
        "## Purpose\n"
        "\n"
        "A small command-line tool used as a lint fixture.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: running the tool.\n"
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


def _cli_md(slug):
    return (
        "# CLI\n"
        "\n"
        "```\n"
        f"{slug} run [--format=json|text]\n"
        "```\n"
        "\n"
        "Exit codes: `0` success, `2` usage error.\n"
    )


def _citing_requirement(rid, slug):
    return (
        f"# {rid}\n"
        "\n"
        f"**{rid}** — The CLI documented in `interface/cli.md` MUST accept "
        "`--format=value` and `--format value`, MUST treat `--format` given "
        "with no value as a usage error returning exit code `2`, and MUST "
        "return exit code `0` on success.\n"
    )


def _plain_requirement(rid):
    return (
        f"# {rid}\n"
        "\n"
        f"**{rid}** — The tool MUST print a single line of output when run.\n"
    )


def _criterion(acid, rid):
    return (
        f"# {acid}\n"
        "\n"
        f"Covers: {rid}\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given the tool is installed\n"
        "When it runs\n"
        "Then it behaves as its requirement states\n"
        "```\n"
    )


def _constraints():
    return (
        "# Constraints\n"
        "\n"
        "- Runs in under one second, measured by timing a single run.\n"
    )


def _build_corpus(root):
    specs = root / "specs"
    _write(
        specs / "glossary.md",
        "# Glossary\n\n- **Fixture** — a synthetic test component.\n",
    )

    # 1. alpha-tool: citing requirement, covered by a criterion -> no finding.
    a = specs / "components" / "alpha-tool"
    _write(a / "component.md", _component_md("alpha-tool"))
    _write(a / "interface" / "cli.md", _cli_md("alpha-tool"))
    _write(a / "requirements" / "R-ALPHA-001.md",
           _citing_requirement("R-ALPHA-001", "alpha-tool"))
    _write(a / "acceptance" / "AC-ALPHA-001.md",
           _criterion("AC-ALPHA-001", "R-ALPHA-001"))
    _write(a / "constraints.md", _constraints())

    # 2. bravo-tool: citing requirement exists, but no criterion covers it.
    b = specs / "components" / "bravo-tool"
    _write(b / "component.md", _component_md("bravo-tool"))
    _write(b / "interface" / "cli.md", _cli_md("bravo-tool"))
    _write(b / "requirements" / "R-BRAVO-001.md",
           _citing_requirement("R-BRAVO-001", "bravo-tool"))
    _write(b / "requirements" / "R-BRAVO-002.md",
           _plain_requirement("R-BRAVO-002"))
    _write(b / "acceptance" / "AC-BRAVO-001.md",
           _criterion("AC-BRAVO-001", "R-BRAVO-002"))
    _write(b / "constraints.md", _constraints())

    # 3. charlie-tool: no requirement cites interface/cli.md at all.
    c = specs / "components" / "charlie-tool"
    _write(c / "component.md", _component_md("charlie-tool"))
    _write(c / "interface" / "cli.md", _cli_md("charlie-tool"))
    _write(c / "requirements" / "R-CHARLIE-001.md",
           _plain_requirement("R-CHARLIE-001"))
    _write(c / "acceptance" / "AC-CHARLIE-001.md",
           _criterion("AC-CHARLIE-001", "R-CHARLIE-001"))
    _write(c / "constraints.md", _constraints())


SLUGS = ["alpha-tool", "bravo-tool", "charlie-tool"]


def _attributed_slugs(finding):
    file_ = str(field(finding, "file") or "").replace("\\", "/")
    message = str(field(finding, "message") or "")
    hits = set()
    for slug in SLUGS:
        if f"components/{slug}/" in file_ or f"comp-{slug}" in message:
            hits.add(slug)
    return hits


def test_r_lint_031_warns_only_for_uncovered_or_uncited_cli(tmp_path):
    repo_root = tmp_path
    _build_corpus(repo_root)

    report = spec_linter.lint(None, repo_root)
    findings = list(field(report, "findings"))

    cli_findings = [f for f in findings if field(f, "rule_id") == "R-LINT-031"]

    per_component = {slug: [] for slug in SLUGS}
    for f in cli_findings:
        slugs = _attributed_slugs(f)
        assert len(slugs) == 1, (
            f"R-LINT-031 finding not attributable to exactly one component: {f!r}"
        )
        per_component[slugs.pop()].append(f)

    assert per_component["alpha-tool"] == [], (
        f"covered CLI component must not get R-LINT-031: "
        f"{per_component['alpha-tool']!r}"
    )
    assert len(per_component["bravo-tool"]) == 1, (
        f"expected one R-LINT-031 finding for bravo-tool, got "
        f"{per_component['bravo-tool']!r}"
    )
    assert len(per_component["charlie-tool"]) == 1, (
        f"expected one R-LINT-031 finding for charlie-tool, got "
        f"{per_component['charlie-tool']!r}"
    )

    for slug in ("bravo-tool", "charlie-tool"):
        f = per_component[slug][0]
        assert field(f, "severity") == "warn", f
        assert f"comp-{slug}" in str(field(f, "message")), f

    assert all(field(f, "severity") == "warn" for f in cli_findings), cli_findings