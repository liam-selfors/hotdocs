"""AC-LINT-020 (Covers: R-LINT-020).

Given comp-foo's frontmatter declares depends_on_guarantees: [G-BAR-001],
G-BAR-001 exists under comp-bar's interface/guarantees/, and comp-foo's
depends_on list does NOT include comp-bar, when the linter runs, then it
fails with R-LINT-018: a guarantee's owner comes from its file's path,
since guarantee files carry no frontmatter.
"""

import json
from pathlib import Path

import pytest

import spec_linter


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _component_body(title: str) -> str:
    return (
        f"# {title}\n"
        "\n"
        "## Purpose\n"
        "\n"
        f"{title} is a synthetic fixture component used to exercise the linter.\n"
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


def _write_component(
    repo: Path,
    slug: str,
    upper: str,
    extra_frontmatter: str = "",
    guarantee: bool = False,
) -> None:
    root = repo / "specs" / "components" / slug
    frontmatter = (
        "---\n"
        f"id: comp-{slug}\n"
        f"title: {slug.capitalize()}\n"
        "status: draft\n"
        "owners: [test-team]\n"
        f"{extra_frontmatter}"
        "sealed: true\n"
        f"source_path: legacy/{slug}/\n"
        "---\n"
    )
    _write(root / "component.md", frontmatter + "\n" + _component_body(slug.capitalize()))
    _write(
        root / "requirements" / f"R-{upper}-001.md",
        f"# R-{upper}-001\n\n**R-{upper}-001** — The {slug} component MUST "
        "behave as characterized.\n",
    )
    _write(
        root / "acceptance" / f"AC-{upper}-001.md",
        f"# AC-{upper}-001\n"
        "\n"
        f"Covers: R-{upper}-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        f"Given the {slug} component\n"
        "When it runs\n"
        "Then it behaves as characterized\n"
        "```\n",
    )
    _write(
        root / "constraints.md",
        "# Constraints\n\nNone beyond the defaults.\n",
    )
    if guarantee:
        _write(
            root / "interface" / "guarantees" / f"G-{upper}-001.md",
            f"# G-{upper}-001\n\n**G-{upper}-001** — The {slug} component MUST "
            "return results in a stable order.\n",
        )


def _build_repo(repo: Path, foo_depends_on_bar: bool) -> Path:
    _write(
        repo / "specs" / "glossary.md",
        "# Glossary\n\n- **Fixture** — a synthetic test corpus.\n",
    )
    foo_extra = ""
    if foo_depends_on_bar:
        foo_extra += "depends_on: [comp-bar]\n"
    foo_extra += "depends_on_guarantees: [G-BAR-001]\n"
    _write_component(repo, "foo", "FOO", extra_frontmatter=foo_extra)
    _write_component(repo, "bar", "BAR", guarantee=True)
    return repo


def _findings(report):
    return list(field(report, "findings"))


def _lint_018_fails(report):
    return [
        f
        for f in _findings(report)
        if field(f, "rule_id") == "R-LINT-018" and field(f, "severity") == "fail"
    ]


def _hard_failures(report):
    return report["hard_failures"] if isinstance(report, dict) else report.hard_failures


def test_guarantee_of_undeclared_dependency_fails_r_lint_018(tmp_path):
    repo = _build_repo(tmp_path / "repo", foo_depends_on_bar=False)

    report = spec_linter.lint(None, repo)

    fails = _lint_018_fails(report)
    assert fails, (
        "expected an R-LINT-018 fail finding; got "
        + repr([(field(f, "rule_id"), field(f, "severity"), field(f, "file"))
                for f in _findings(report)])
    )
    files = [str(field(f, "file")).replace("\\", "/") for f in fails]
    assert any(p.endswith("specs/components/foo/component.md") for p in files), files
    # No R-LINT-018 finding is attributed to comp-bar, which did nothing wrong.
    assert not any("specs/components/bar/" in p for p in files), files
    assert _hard_failures(report) >= 1


def test_guarantee_of_declared_dependency_passes_r_lint_018(tmp_path):
    # Control: same corpus, but comp-foo now lists comp-bar in depends_on.
    # The guarantee's owner (comp-bar, from its file path) is then a declared
    # dependency, so R-LINT-018 must not fire.
    repo = _build_repo(tmp_path / "repo", foo_depends_on_bar=True)

    report = spec_linter.lint(None, repo)

    assert _lint_018_fails(report) == [], [
        (field(f, "rule_id"), field(f, "file"), field(f, "message"))
        for f in _lint_018_fails(report)
    ]


def test_cli_exits_1_and_reports_r_lint_018(tmp_path, capsys):
    repo = _build_repo(tmp_path / "repo", foo_depends_on_bar=False)

    code = spec_linter.main(["--format=json", f"--repo-root={repo}"])

    assert code == 1
    out = capsys.readouterr().out
    doc = json.loads(out)
    rule_ids = [
        (f["rule_id"], f["severity"]) for f in doc["findings"]
    ]
    assert ("R-LINT-018", "fail") in rule_ids, rule_ids
    assert doc["summary"]["hard_failures"] >= 1