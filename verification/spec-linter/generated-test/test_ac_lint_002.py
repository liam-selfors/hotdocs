"""AC-LINT-002: a ratified component.md with a non-empty "Open questions"
section yields a fail-severity finding for rule R-LINT-002."""

import io
import json
import contextlib
from pathlib import Path

import spec_linter


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


SLUG = "widget"
COMP_ID = "comp-widget"


def _component_md(open_questions_body: str) -> str:
    return (
        "---\n"
        f"id: {COMP_ID}\n"
        "title: Widget\n"
        "status: ratified\n"
        "owners: [pipeline-team]\n"
        "sealed: true\n"
        "source_path: legacy/widget/\n"
        "last_ratified_commit: 0123456789abcdef0123456789abcdef01234567\n"
        "---\n"
        "\n"
        "# Widget\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Widget turns an input string into an upper-case output string.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: upper-casing strings.\n"
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
        f"{open_questions_body}"
        "## Change log\n"
        "\n"
        "- Initial draft.\n"
    )


def _build_repo(root: Path, open_questions_body: str) -> Path:
    specs = root / "specs"
    comp = specs / "components" / SLUG
    (comp / "requirements").mkdir(parents=True)
    (comp / "acceptance").mkdir(parents=True)

    (comp / "component.md").write_text(_component_md(open_questions_body))
    (comp / "requirements" / "R-WIDGET-001.md").write_text(
        "# R-WIDGET-001\n"
        "\n"
        "**R-WIDGET-001** — The widget MUST return its input upper-cased.\n"
    )
    (comp / "acceptance" / "AC-WIDGET-001.md").write_text(
        "# AC-WIDGET-001\n"
        "\n"
        "Covers: R-WIDGET-001\n"
        "Kind: compiled\n"
        "\n"
        "```gherkin\n"
        "Given the input \"abc\"\n"
        "When the widget runs\n"
        "Then the output is \"ABC\"\n"
        "```\n"
    )
    (comp / "constraints.md").write_text(
        "# Constraints\n"
        "\n"
        "- Upper-casing a 1 KiB string MUST take under 10 ms, measured by a benchmark.\n"
    )
    (specs / "glossary.md").write_text(
        "# Glossary\n"
        "\n"
        "- **Widget** — the thing under test.\n"
    )
    return root


def _r_lint_002_findings(report):
    findings = field(report, "findings")
    return [f for f in findings if field(f, "rule_id") == "R-LINT-002"]


def _is_widget_root(file_value) -> bool:
    return str(file_value).replace("\\", "/").endswith(
        f"specs/components/{SLUG}/component.md"
    )


def test_ratified_with_open_questions_fails_r_lint_002(tmp_path):
    repo_root = _build_repo(
        tmp_path / "repo",
        "- Should the widget also handle lower-casing?\n\n",
    )

    report = spec_linter.lint(None, repo_root)

    hits = _r_lint_002_findings(report)
    fail_hits = [f for f in hits if field(f, "severity") == "fail"]
    assert fail_hits, (
        "expected a fail-severity R-LINT-002 finding, got: "
        f"{[(field(f, 'rule_id'), field(f, 'severity'), field(f, 'file')) for f in field(report, 'findings')]}"
    )
    assert any(_is_widget_root(field(f, "file")) for f in fail_hits), (
        f"R-LINT-002 finding not reported on the component.md: "
        f"{[field(f, 'file') for f in fail_hits]}"
    )

    hard = report["hard_failures"] if isinstance(report, dict) else report.hard_failures
    assert hard >= 1


def test_ratified_with_empty_open_questions_has_no_r_lint_002(tmp_path):
    # Control: identical fixture (ratified, last_ratified_commit present)
    # but with an empty "Open questions" section must not trip R-LINT-002.
    repo_root = _build_repo(tmp_path / "repo", "")

    report = spec_linter.lint(None, repo_root)

    hits = [
        f
        for f in _r_lint_002_findings(report)
        if field(f, "severity") == "fail" and _is_widget_root(field(f, "file"))
    ]
    assert hits == [], f"unexpected R-LINT-002 findings: {hits}"


def test_cli_json_report_contains_r_lint_002_fail(tmp_path):
    repo_root = _build_repo(
        tmp_path / "repo",
        "- Should the widget also handle lower-casing?\n\n",
    )

    out = io.StringIO()
    err = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = spec_linter.main(["--format=json", f"--repo-root={repo_root}"])

    assert code == 1, f"expected exit 1, got {code}; stderr: {err.getvalue()}"
    doc = json.loads(out.getvalue())
    fail_hits = [
        f
        for f in doc["findings"]
        if f["rule_id"] == "R-LINT-002" and f["severity"] == "fail"
    ]
    assert fail_hits, f"no fail-severity R-LINT-002 finding in JSON: {doc}"
    assert any(_is_widget_root(f["file"]) for f in fail_hits)
    assert doc["summary"]["hard_failures"] >= 1