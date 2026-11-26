# hotdocs-criterion: sha256:ded549a0d6fc894327b5432a7ddd135a0a5736fd768b3f6c58ce1afd901e2128
"""AC-LINT-020: depends_on_guarantees whose owner (derived from the guarantee
file's path) is not in depends_on fails with R-LINT-018."""

from pathlib import Path

import spec_linter


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _component_md(comp_id, slug, extra_lines):
    lines = [
        "---",
        "id: " + comp_id,
        "title: " + slug.capitalize() + " Component",
        "status: draft",
        "owners: [test-team]",
    ]
    lines.extend(extra_lines)
    lines.extend(
        [
            "sealed: true",
            "source_path: legacy/" + slug + "/",
            "---",
            "",
            "# " + slug,
            "",
            "## Purpose",
            "",
            "A small fixture component used for testing.",
            "",
            "## Scope",
            "",
            "- In scope: testing.",
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
    )
    return "\n".join(lines)


def _requirement(req_id):
    return (
        "# " + req_id + "\n\n"
        "**" + req_id + "** — The component MUST do its one thing.\n"
    )


def _acceptance(ac_id, req_id):
    return (
        "# " + ac_id + "\n\n"
        "Covers: " + req_id + "\n"
        "Kind: generated-test\n\n"
        "```gherkin\n"
        "Given an input\n"
        "When the component runs\n"
        "Then it does its one thing\n"
        "```\n"
    )


def _build_corpus(repo_root, foo_depends_on_bar):
    specs = repo_root / "specs"
    _write(
        specs / "glossary.md",
        "# Glossary\n\n- **Widget** — a thing used in tests.\n",
    )

    # comp-bar: owns G-BAR-001 under interface/guarantees/
    bar = specs / "components" / "bar"
    _write(bar / "component.md", _component_md("comp-bar", "bar", ["depends_on: []"]))
    _write(bar / "requirements" / "R-BAR-001.md", _requirement("R-BAR-001"))
    _write(bar / "acceptance" / "AC-BAR-001.md", _acceptance("AC-BAR-001", "R-BAR-001"))
    _write(
        bar / "interface" / "guarantees" / "G-BAR-001.md",
        "# G-BAR-001\n\n"
        "**G-BAR-001** — Every call MUST be idempotent.\n",
    )
    _write(
        bar / "constraints.md",
        "# Constraints\n\n- Latency under 1s, measured by a timer.\n",
    )

    # comp-foo: relies on G-BAR-001
    foo = specs / "components" / "foo"
    depends = "depends_on: [comp-bar]" if foo_depends_on_bar else "depends_on: []"
    _write(
        foo / "component.md",
        _component_md(
            "comp-foo",
            "foo",
            [depends, "depends_on_guarantees: [G-BAR-001]"],
        ),
    )
    _write(foo / "requirements" / "R-FOO-001.md", _requirement("R-FOO-001"))
    _write(foo / "acceptance" / "AC-FOO-001.md", _acceptance("AC-FOO-001", "R-FOO-001"))
    _write(
        foo / "constraints.md",
        "# Constraints\n\n- Latency under 1s, measured by a timer.\n",
    )


def _lint_018_fails(report):
    out = []
    for finding in field(report, "findings"):
        if field(finding, "rule_id") == "R-LINT-018" and field(finding, "severity") == "fail":
            out.append(finding)
    return out


def test_guarantee_owner_not_in_depends_on_fails_r_lint_018(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_corpus(repo_root, foo_depends_on_bar=False)

    report = spec_linter.lint(None, repo_root)

    failures = _lint_018_fails(report)
    assert failures, "expected an R-LINT-018 fail finding, got: " + repr(
        [(field(f, "rule_id"), field(f, "severity"), field(f, "message")) for f in field(report, "findings")]
    )
    assert any(
        ("G-BAR-001" in field(f, "message")) or ("comp-bar" in field(f, "message"))
        for f in failures
    )
    assert field(report, "hard_failures") >= 1

    code = spec_linter.main(["--repo-root=" + str(repo_root)])
    assert code == 1


def test_guarantee_owner_listed_in_depends_on_passes_r_lint_018(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_corpus(repo_root, foo_depends_on_bar=True)

    report = spec_linter.lint(None, repo_root)

    r018 = [f for f in field(report, "findings") if field(f, "rule_id") == "R-LINT-018"]
    assert r018 == [], "unexpected R-LINT-018 findings: " + repr(
        [field(f, "message") for f in r018]
    )