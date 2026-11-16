"""AC-LINT-018: a depends_on_guarantees entry whose owning component is not in
this component's own depends_on is a fail-severity R-LINT-018 finding naming
the owning component by its comp-<slug> id."""

import spec_linter

from pathlib import Path


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _component_md(slug: str, title: str, extra_frontmatter: str = "") -> str:
    return (
        "---\n"
        f"id: comp-{slug}\n"
        f"title: {title}\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "sealed: true\n"
        f"source_path: legacy/{slug}/\n"
        f"{extra_frontmatter}"
        "---\n"
        "\n"
        f"# {title}\n"
        "\n"
        "## Purpose\n"
        "\n"
        f"A small synthetic component used only as a lint fixture.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: fixture behavior.\n"
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


def _write_component(root: Path, slug: str, upper: str, extra_frontmatter: str = "") -> None:
    cdir = root / "specs" / "components" / slug
    _write(cdir / "component.md", _component_md(slug, f"{slug.capitalize()} Component", extra_frontmatter))
    _write(
        cdir / "requirements" / f"R-{upper}-001.md",
        f"# R-{upper}-001\n\n"
        f"**R-{upper}-001** — The component MUST match existing behavior.\n",
    )
    _write(
        cdir / "acceptance" / f"AC-{upper}-001.md",
        f"# AC-{upper}-001\n\n"
        f"Covers: R-{upper}-001\n"
        "Kind: generated-test\n\n"
        "```gherkin\n"
        "Given the component\n"
        "When it runs\n"
        "Then it matches existing behavior\n"
        "```\n",
    )
    _write(
        cdir / "constraints.md",
        "# Constraints\n\n- None beyond existing behavior.\n",
    )


def _build_repo(root: Path, foo_depends_on_bar: bool) -> None:
    _write(
        root / "specs" / "glossary.md",
        "# Glossary\n\n- **Fixture** — a synthetic test corpus.\n",
    )
    # bar owns guarantee G-BAR-001.
    _write_component(root, "bar", "BAR")
    _write(
        root / "specs" / "components" / "bar" / "interface" / "guarantees" / "G-BAR-001.md",
        "# G-BAR-001\n\n"
        "**G-BAR-001** — The bar component MUST return results in a stable order.\n",
    )
    # foo relies on G-BAR-001; depends_on either omits or includes comp-bar.
    deps = "depends_on: [comp-bar]\n" if foo_depends_on_bar else "depends_on: []\n"
    _write_component(
        root,
        "foo",
        "FOO",
        extra_frontmatter=deps + "depends_on_guarantees: [G-BAR-001]\n",
    )


def _lint018_findings(report):
    findings = field(report, "findings")
    return [f for f in findings if field(f, "rule_id") == "R-LINT-018"]


def test_guarantee_owner_missing_from_depends_on_fails_naming_comp_bar(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_repo(repo_root, foo_depends_on_bar=False)

    report = spec_linter.lint(None, repo_root)

    lint018 = _lint018_findings(report)
    matching = [
        f
        for f in lint018
        if field(f, "severity") == "fail" and "comp-bar" in field(f, "message")
    ]
    assert matching, (
        "expected a fail-severity R-LINT-018 finding naming comp-bar; got "
        f"{[(field(f, 'severity'), field(f, 'message')) for f in lint018]}"
    )
    assert field(report, "hard_failures") >= 1


def test_guarantee_owner_listed_in_depends_on_has_no_missing_dependency_finding(tmp_path):
    # Control: the same corpus with comp-bar in depends_on must not produce the
    # missing-dependency finding, so the finding above is caused by the omission.
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_repo(repo_root, foo_depends_on_bar=True)

    report = spec_linter.lint(None, repo_root)

    lint018 = _lint018_findings(report)
    naming_bar = [
        f
        for f in lint018
        if field(f, "severity") == "fail" and "comp-bar" in field(f, "message")
    ]
    assert naming_bar == [], (
        "did not expect an R-LINT-018 finding naming comp-bar when it is in "
        f"depends_on; got {[field(f, 'message') for f in naming_bar]}"
    )
    # G-BAR-001 exists, so no R-LINT-018 failure of any kind is expected.
    assert [f for f in lint018 if field(f, "severity") == "fail"] == []