# hotdocs-criterion: sha256:3eaf0ef739ca02059572fc91b80d5828f9922d8317109246e5cde15f34ee6e6c
"""AC-LINT-020: a depends_on_guarantees entry whose owning component (derived
from the guarantee file's path, since guarantee files carry no frontmatter) is
not listed in depends_on fails with R-LINT-018."""

from pathlib import Path

import spec_linter


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _component_md(comp_id, title, extra_lines):
    lines = [
        "---",
        "id: " + comp_id,
        "title: " + title,
        "status: draft",
        "owners: [pipeline-team]",
        "sealed: true",
        "source_path: legacy/" + comp_id + "/",
    ]
    lines.extend(extra_lines)
    lines.append("---")
    lines.append("")
    lines.append("# " + title)
    lines.append("")
    lines.append("## Purpose")
    lines.append("")
    lines.append("Matches existing behavior; do not regenerate.")
    lines.append("")
    lines.append("## Scope")
    lines.append("")
    lines.append("- In scope: existing behavior.")
    lines.append("- Out of scope: everything else.")
    lines.append("")
    lines.append("## Definitions")
    lines.append("")
    lines.append("None.")
    lines.append("")
    lines.append("## Behavior")
    lines.append("")
    lines.append("See `requirements/`.")
    lines.append("")
    lines.append("## Interfaces")
    lines.append("")
    lines.append("See `interface/`.")
    lines.append("")
    lines.append("## Data")
    lines.append("")
    lines.append("See `interface/data/`.")
    lines.append("")
    lines.append("## Acceptance criteria")
    lines.append("")
    lines.append("See `acceptance/`.")
    lines.append("")
    lines.append("## Non-functional constraints")
    lines.append("")
    lines.append("See `constraints.md`.")
    lines.append("")
    lines.append("## Open questions")
    lines.append("")
    lines.append("## Change log")
    lines.append("")
    lines.append("- Initial draft.")
    lines.append("")
    return "\n".join(lines)


def _build_fixture(repo_root, foo_depends_on_bar):
    specs = repo_root / "specs"
    _write(specs / "glossary.md", "# Glossary\n\n- **Widget** — a thing.\n")

    # comp-bar: owns guarantee G-BAR-001 under its interface/guarantees/.
    bar = specs / "components" / "bar"
    _write(bar / "component.md", _component_md("comp-bar", "Bar", []))
    _write(
        bar / "interface" / "guarantees" / "G-BAR-001.md",
        "# G-BAR-001\n\nBar MUST return results in a stable order.\n",
    )
    _write(
        bar / "constraints.md",
        "# Constraints\n\nNone beyond existing behavior.\n",
    )

    # comp-foo: relies on G-BAR-001.
    extra = ["depends_on_guarantees: [G-BAR-001]"]
    if foo_depends_on_bar:
        extra.insert(0, "depends_on: [comp-bar]")
    foo = specs / "components" / "foo"
    _write(foo / "component.md", _component_md("comp-foo", "Foo", extra))
    _write(
        foo / "constraints.md",
        "# Constraints\n\nNone beyond existing behavior.\n",
    )


def _lint018_fail_findings(report):
    out = []
    for finding in field(report, "findings"):
        if field(finding, "rule_id") == "R-LINT-018" and field(finding, "severity") == "fail":
            out.append(finding)
    return out


def test_guarantee_owner_not_in_depends_on_fails_r_lint_018(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root, foo_depends_on_bar=False)

    report = spec_linter.lint(None, repo_root)

    failures = _lint018_fail_findings(report)
    assert failures, (
        "expected an R-LINT-018 fail finding: G-BAR-001 is owned by comp-bar "
        "(from its path) but comp-foo does not list comp-bar in depends_on; got "
        + repr([(field(f, "rule_id"), field(f, "severity"), field(f, "file"), field(f, "message"))
                for f in field(report, "findings")])
    )
    assert any("components/foo/" in str(field(f, "file")).replace("\\", "/") for f in failures), (
        "the R-LINT-018 finding should be reported against comp-foo; got "
        + repr([field(f, "file") for f in failures])
    )
    assert field(report, "hard_failures") >= 1


def test_guarantee_owner_listed_in_depends_on_has_no_r_lint_018(tmp_path):
    # Control: the same corpus, with comp-bar in comp-foo's depends_on, resolves
    # G-BAR-001's owner from its path and so produces no R-LINT-018 failure.
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root, foo_depends_on_bar=True)

    report = spec_linter.lint(None, repo_root)

    failures = _lint018_fail_findings(report)
    assert failures == [], (
        "no R-LINT-018 failure expected when the guarantee's owner is in depends_on; got "
        + repr([(field(f, "file"), field(f, "message")) for f in failures])
    )