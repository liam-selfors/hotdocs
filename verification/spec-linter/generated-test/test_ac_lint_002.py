# hotdocs-criterion: sha256:01c1d8473761a8f0f84cc05f053a918362e8f518dc767e5bac88c18e857d5bab
"""AC-LINT-002: a ratified component.md with a non-empty "Open questions"
section yields a fail-severity finding for rule R-LINT-002."""

from pathlib import Path

import spec_linter


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _sev(value):
    sev = field(value, "severity")
    return getattr(sev, "value", sev)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_fixture(repo_root: Path, open_questions: str) -> Path:
    specs = repo_root / "specs"
    _write(
        specs / "glossary.md",
        "# Glossary\n\n- **Widget** — a small thing used in tests.\n",
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
        "Foo does a small thing for tests.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: the small thing.\n"
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
        + open_questions
        + "\n"
        "## Change log\n"
        "\n"
        "- Initial draft.\n"
    )
    _write(comp / "component.md", component_md)
    _write(
        comp / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n\n**R-FOO-001** — Foo MUST do the small thing.\n",
    )
    _write(
        comp / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n"
        "\n"
        "Covers: R-FOO-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given foo\n"
        "When the small thing is requested\n"
        "Then foo does the small thing\n"
        "```\n",
    )
    _write(
        comp / "constraints.md",
        "# Constraints\n\n- None beyond defaults; measured by inspection.\n",
    )
    return comp / "component.md"


def _lint_002_findings(report):
    findings = field(report, "findings")
    return [f for f in findings if field(f, "rule_id") == "R-LINT-002"]


def test_ratified_with_open_questions_fails_r_lint_002(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(
        repo_root,
        "- Should foo also do the big thing?\n",
    )

    report = spec_linter.lint(None, repo_root)

    matches = _lint_002_findings(report)
    fails = [f for f in matches if _sev(f) == "fail"]
    assert fails, (
        "expected a fail-severity R-LINT-002 finding, got: "
        + repr(field(report, "findings"))
    )
    assert any(
        "components/foo/component.md" in str(field(f, "file")).replace("\\", "/")
        for f in fails
    )
    assert field(report, "hard_failures") >= 1


def test_ratified_with_empty_open_questions_has_no_r_lint_002(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root, "")

    report = spec_linter.lint(None, repo_root)

    fails = [f for f in _lint_002_findings(report) if _sev(f) == "fail"]
    assert fails == [], "unexpected R-LINT-002 findings: " + repr(fails)