# hotdocs-criterion: sha256:b681e631b03702cb4951ffe0fa292c8bc62e19f0b5e1a94d2043f007c19fc04c
from pathlib import Path

import spec_linter


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def component_md(comp_id, title, extra_lines):
    lines = [
        "---",
        "id: " + comp_id,
        "title: " + title,
        "status: draft",
        "owners: [pipeline-team]",
    ]
    lines.extend(extra_lines)
    lines.extend([
        "sealed: true",
        "source_path: legacy/" + comp_id[len("comp-"):] + "/",
        "---",
        "",
        "# " + title,
        "",
        "## Purpose",
        "",
        "A small fixture component used to exercise the linter.",
        "",
        "## Scope",
        "",
        "- In scope: fixture behavior.",
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
    ])
    return "\n".join(lines)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_fixture(root):
    specs = root / "specs"
    write(
        specs / "glossary.md",
        "# Glossary\n\n- **Fixture term** — a term used only by this fixture.\n",
    )

    bar = specs / "components" / "bar"
    write(bar / "component.md", component_md("comp-bar", "Bar", []))
    write(
        bar / "interface" / "guarantees" / "G-BAR-001.md",
        "# G-BAR-001\n\n**G-BAR-001** — Bar MUST return the same result "
        "for the same input.\n",
    )
    write(
        bar / "constraints.md",
        "# Constraints\n\nNone.\n",
    )

    foo = specs / "components" / "foo"
    write(
        foo / "component.md",
        component_md(
            "comp-foo",
            "Foo",
            [
                "depends_on: []",
                "depends_on_guarantees: [G-BAR-001]",
            ],
        ),
    )
    write(
        foo / "constraints.md",
        "# Constraints\n\nNone.\n",
    )


def test_ac_lint_018_guarantee_owner_not_in_depends_on(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root)

    report = spec_linter.lint(None, repo_root)
    findings = list(field(report, "findings"))

    matching = [
        f for f in findings
        if field(f, "rule_id") == "R-LINT-018"
        and field(f, "severity") == "fail"
        and "comp-bar" in str(field(f, "message"))
    ]
    assert matching, (
        "expected a fail-severity R-LINT-018 finding naming comp-bar; got: "
        + repr([
            (field(f, "rule_id"), field(f, "severity"), field(f, "message"))
            for f in findings
        ])
    )
    assert field(report, "hard_failures") >= 1