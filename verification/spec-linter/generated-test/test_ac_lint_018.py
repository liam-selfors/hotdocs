# hotdocs-criterion: sha256:fa4cf421e48e617fbb352eb0bee6a456e7a58281e1fd9909d92058c4707deed2
from pathlib import Path

import spec_linter


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _text(value):
    value = getattr(value, "value", value)
    return str(value)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _component_md(comp_id, title, slug, extra_lines):
    lines = [
        "---",
        "id: " + comp_id,
        "title: " + title,
        "status: draft",
        "owners: [pipeline-team]",
        "sealed: true",
        "source_path: legacy/" + slug + "/",
    ]
    lines.extend(extra_lines)
    lines.append("---")
    body = [
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
    ]
    return "\n".join(lines + body)


def _add_units(comp_dir, prefix):
    req_id = "R-" + prefix + "-001"
    ac_id = "AC-" + prefix + "-001"
    _write(
        comp_dir / "requirements" / (req_id + ".md"),
        "# " + req_id + "\n\n**" + req_id + "** — The component MUST "
        "match existing behavior.\n",
    )
    _write(
        comp_dir / "acceptance" / (ac_id + ".md"),
        "# " + ac_id + "\n\nCovers: " + req_id + "\nKind: compiled\n\n"
        "```gherkin\nGiven the component\nWhen it runs\n"
        "Then it matches existing behavior\n```\n",
    )
    _write(
        comp_dir / "constraints.md",
        "# Constraints\n\nNone.\n",
    )


def _build_corpus(repo_root, foo_depends_on_bar):
    specs = repo_root / "specs"
    _write(
        specs / "glossary.md",
        "# Glossary\n\n- **Fixture** — a synthetic spec corpus.\n",
    )

    bar_dir = specs / "components" / "bar"
    _write(bar_dir / "component.md", _component_md("comp-bar", "Bar", "bar", []))
    _add_units(bar_dir, "BAR")
    _write(
        bar_dir / "interface" / "guarantees" / "G-BAR-001.md",
        "# G-BAR-001\n\n**G-BAR-001** — Bar MUST return results in a "
        "stable order.\n",
    )

    foo_extra = []
    if foo_depends_on_bar:
        foo_extra.append("depends_on: [comp-bar]")
    foo_extra.append("depends_on_guarantees: [G-BAR-001]")
    foo_dir = specs / "components" / "foo"
    _write(foo_dir / "component.md", _component_md("comp-foo", "Foo", "foo", foo_extra))
    _add_units(foo_dir, "FOO")


def _r018_fail_findings(report):
    result = []
    for finding in field(report, "findings"):
        if _text(field(finding, "rule_id")) != "R-LINT-018":
            continue
        if _text(field(finding, "severity")) != "fail":
            continue
        result.append(finding)
    return result


def test_guarantee_of_undeclared_dependency_fails_naming_owner(tmp_path):
    repo_root = Path(tmp_path)
    _build_corpus(repo_root, foo_depends_on_bar=False)

    report = spec_linter.lint(None, repo_root)

    matches = _r018_fail_findings(report)
    assert matches, (
        "expected a fail-severity R-LINT-018 finding, got: "
        + repr([(field(f, "rule_id"), field(f, "severity"), field(f, "message"))
                for f in field(report, "findings")])
    )
    assert any("comp-bar" in _text(field(f, "message")) for f in matches), repr(
        [field(f, "message") for f in matches]
    )
    assert field(report, "hard_failures") >= 1


def test_guarantee_of_declared_dependency_has_no_r018_failure(tmp_path):
    repo_root = Path(tmp_path)
    _build_corpus(repo_root, foo_depends_on_bar=True)

    report = spec_linter.lint(None, repo_root)

    matches = _r018_fail_findings(report)
    assert matches == [], repr([field(f, "message") for f in matches])