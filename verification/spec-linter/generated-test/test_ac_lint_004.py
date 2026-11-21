# hotdocs-criterion: sha256:9f10595e2fe8b271d76759c5acbede70c0a7448eff0283bafde928fc8e26205d
import spec_linter


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _component_md(slug, depends_on):
    lines = [
        "---",
        "id: comp-" + slug,
        "title: " + slug.capitalize() + " Component",
        "status: draft",
        "owners: [test-team]",
        "depends_on: [" + ", ".join(depends_on) + "]",
        "sealed: true",
        "source_path: legacy/" + slug + "/",
        "---",
        "",
        "# " + slug.capitalize() + " Component",
        "",
        "## Purpose",
        "",
        "Matches existing behavior; do not regenerate.",
        "",
        "## Scope",
        "",
        "- In scope: existing behavior.",
        "- Out of scope: everything else.",
        "",
        "## Definitions",
        "",
        "None.",
        "",
        "## Behavior",
        "",
        "See `requirements/`.",
        "",
        "## Interfaces",
        "",
        "See `interface/`.",
        "",
        "## Data",
        "",
        "See `interface/data/`.",
        "",
        "## Acceptance criteria",
        "",
        "See `acceptance/`.",
        "",
        "## Non-functional constraints",
        "",
        "See `constraints.md`.",
        "",
        "## Open questions",
        "",
        "## Change log",
        "",
        "- Initial draft.",
        "",
    ]
    return "\n".join(lines)


def _build_corpus(repo_root):
    specs = repo_root / "specs"
    (specs / "product").mkdir(parents=True)
    (specs / "architecture").mkdir(parents=True)
    (specs / "vars").mkdir(parents=True)
    (specs / "decisions").mkdir(parents=True)
    (specs / "glossary.md").write_text(
        "# Glossary\n\n- **Widget** — a test term.\n", encoding="utf-8"
    )
    for slug, dep in (("alpha", "comp-beta"), ("beta", "comp-alpha")):
        comp_dir = specs / "components" / slug
        comp_dir.mkdir(parents=True)
        (comp_dir / "component.md").write_text(
            _component_md(slug, [dep]), encoding="utf-8"
        )


def test_ac_lint_004_depends_on_cycle_reported_naming_both_components(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_corpus(repo_root)

    report = spec_linter.lint(None, repo_root)
    findings = list(field(report, "findings"))

    cycle_findings = [
        f
        for f in findings
        if field(f, "rule_id") == "R-LINT-004" and field(f, "severity") == "fail"
    ]
    assert cycle_findings, (
        "expected a fail-severity R-LINT-004 finding, got: "
        + repr([(field(f, "rule_id"), field(f, "severity"), field(f, "message")) for f in findings])
    )

    naming_both = [
        f
        for f in cycle_findings
        if "comp-alpha" in str(field(f, "message"))
        and "comp-beta" in str(field(f, "message"))
    ]
    assert naming_both, (
        "expected an R-LINT-004 finding naming both comp-alpha and comp-beta, got: "
        + repr([field(f, "message") for f in cycle_findings])
    )

    assert field(report, "hard_failures") >= 1