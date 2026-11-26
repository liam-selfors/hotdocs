# hotdocs-criterion: sha256:158c6b3f2c66947253fa8f7b5a8a13519a0c4beb8d8da6b2c4e3338b9111a14c
"""AC-LINT-004: a depends_on cycle (A -> B -> A) yields a fail-severity
R-LINT-004 finding naming both components by their comp-<slug> ids."""

from pathlib import Path

import spec_linter


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _component_md(slug, depends_on):
    deps = "[" + ", ".join(depends_on) + "]"
    return (
        "---\n"
        "id: comp-" + slug + "\n"
        "title: " + slug.capitalize() + " Component\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "depends_on: " + deps + "\n"
        "sealed: true\n"
        "source_path: legacy/" + slug + "/\n"
        "---\n"
        "\n"
        "# " + slug.capitalize() + " Component\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Provides the " + slug + " behavior for the fixture corpus.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: the " + slug + " behavior.\n"
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


def _write_component(repo_root, slug, depends_on):
    upper = slug.upper()
    root = repo_root / "specs" / "components" / slug
    (root / "requirements").mkdir(parents=True, exist_ok=True)
    (root / "acceptance").mkdir(parents=True, exist_ok=True)
    (root / "component.md").write_text(_component_md(slug, depends_on))
    req_id = "R-" + upper + "-001"
    ac_id = "AC-" + upper + "-001"
    (root / "requirements" / (req_id + ".md")).write_text(
        "# " + req_id + "\n\n"
        "**" + req_id + "** — The component MUST return the value it is given.\n"
    )
    (root / "acceptance" / (ac_id + ".md")).write_text(
        "# " + ac_id + "\n\n"
        "Covers: " + req_id + "\n"
        "Kind: generated-test\n\n"
        "```gherkin\n"
        "Given a value 1\n"
        "When the component is called with it\n"
        "Then it returns 1\n"
        "```\n"
    )
    (root / "constraints.md").write_text(
        "# Constraints\n\n- None beyond the defaults.\n"
    )


def _build_corpus(repo_root, alpha_deps, beta_deps):
    specs = repo_root / "specs"
    specs.mkdir(parents=True, exist_ok=True)
    (specs / "glossary.md").write_text(
        "# Glossary\n\n- **Widget** — a fixture term.\n"
    )
    _write_component(repo_root, "alpha", alpha_deps)
    _write_component(repo_root, "beta", beta_deps)


def _cycle_findings(report):
    return [
        f for f in field(report, "findings")
        if field(f, "rule_id") == "R-LINT-004"
    ]


def test_depends_on_cycle_reports_fail_naming_both(tmp_path):
    repo_root = tmp_path / "repo"
    _build_corpus(repo_root, ["comp-beta"], ["comp-alpha"])

    report = spec_linter.lint(None, repo_root)

    cycle = _cycle_findings(report)
    assert cycle, "expected an R-LINT-004 finding for the alpha<->beta cycle"
    naming_both = [
        f for f in cycle
        if field(f, "severity") == "fail"
        and "comp-alpha" in str(field(f, "message"))
        and "comp-beta" in str(field(f, "message"))
    ]
    assert naming_both, (
        "no fail-severity R-LINT-004 finding names both comp-alpha and "
        "comp-beta: " + repr([str(field(f, "message")) for f in cycle])
    )
    assert field(report, "hard_failures") >= 1


def test_acyclic_depends_on_reports_no_cycle(tmp_path):
    repo_root = tmp_path / "repo"
    _build_corpus(repo_root, ["comp-beta"], [])

    report = spec_linter.lint(None, repo_root)

    assert _cycle_findings(report) == []