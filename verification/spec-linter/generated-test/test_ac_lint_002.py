# hotdocs-criterion: sha256:deb69f149877609e3b9574697194f3699eeb1011c9c1207031cf8f288691b8db
"""AC-LINT-002: a ratified component with a non-empty "Open questions"
section yields a fail-severity finding for rule R-LINT-002."""

import json
from pathlib import Path

import spec_linter


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_corpus(repo_root, open_questions_body):
    specs = repo_root / "specs"
    _write(
        specs / "glossary.md",
        "# Glossary\n"
        "\n"
        "- **Widget** \u2014 a thing the foo component handles.\n",
    )
    comp = specs / "components" / "foo"
    component_md = (
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: ratified\n"
        "owners: [pipeline-team]\n"
        "sealed: true\n"
        "source_path: legacy/foo/\n"
        "last_ratified_commit: 0000000\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Foo handles widgets for its callers.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: widgets.\n"
        "- Out of scope: everything else.\n"
        "\n"
        "## Definitions\n"
        "\n"
        "None beyond the glossary.\n"
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
        + open_questions_body
        + "## Change log\n"
        "\n"
        "- Initial draft.\n"
    )
    _write(comp / "component.md", component_md)
    _write(
        comp / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n"
        "\n"
        "**R-FOO-001** \u2014 Foo MUST handle every widget it is given.\n",
    )
    _write(
        comp / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n"
        "\n"
        "Covers: R-FOO-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given a widget\n"
        "When foo handles it\n"
        "Then the widget is handled\n"
        "```\n",
    )
    _write(
        comp / "constraints.md",
        "# Constraints\n"
        "\n"
        "- Handles a widget in under 1 second, measured by a timer.\n",
    )
    return comp / "component.md"


def _lint_002_fails(findings):
    return [
        f
        for f in findings
        if field(f, "rule_id") == "R-LINT-002" and field(f, "severity") == "fail"
    ]


def test_ratified_with_open_questions_fails_r_lint_002(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_corpus(
        repo_root,
        "- Should foo also handle gadgets?\n\n",
    )

    report = spec_linter.lint(None, repo_root)

    hits = _lint_002_fails(field(report, "findings"))
    assert hits, "expected a fail-severity R-LINT-002 finding, got: " + repr(
        field(report, "findings")
    )
    assert field(report, "hard_failures") >= 1
    assert any(
        str(field(f, "file")).replace("\\", "/").endswith("components/foo/component.md")
        for f in hits
    )


def test_ratified_with_empty_open_questions_has_no_r_lint_002(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_corpus(repo_root, "")

    report = spec_linter.lint(None, repo_root)

    assert _lint_002_fails(field(report, "findings")) == [], repr(
        field(report, "findings")
    )


def test_cli_reports_r_lint_002_and_exits_1(tmp_path, capsys):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_corpus(
        repo_root,
        "- Should foo also handle gadgets?\n\n",
    )

    code = spec_linter.main(["--format=json", "--repo-root=" + str(repo_root)])
    out = capsys.readouterr().out

    assert code == 1
    data = json.loads(out)
    hits = _lint_002_fails(data["findings"])
    assert hits, "expected a fail-severity R-LINT-002 finding in JSON: " + out
    assert data["summary"]["hard_failures"] >= 1