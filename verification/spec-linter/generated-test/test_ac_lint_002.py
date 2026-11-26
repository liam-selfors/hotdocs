# hotdocs-criterion: sha256:7d3f5fcab30ccc42adb9c74bedc644a977160cec2db667047ff227bfc5bb8fca
import json
from pathlib import Path

import spec_linter


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _component_md(open_questions_body):
    return (
        "---\n"
        + "id: comp-foo\n"
        + "title: Foo\n"
        + "status: ratified\n"
        + "owners: [pipeline-team]\n"
        + "depends_on: []\n"
        + "sealed: true\n"
        + "source_path: legacy/foo/\n"
        + "last_ratified_commit: 0000000\n"
        + "---\n"
        + "\n"
        + "# Foo\n"
        + "\n"
        + "## Purpose\n"
        + "\n"
        + "Foo does a small thing for its callers.\n"
        + "\n"
        + "## Scope\n"
        + "\n"
        + "- In scope: the small thing.\n"
        + "- Out of scope: everything else.\n"
        + "\n"
        + "## Definitions\n"
        + "\n"
        + "None.\n"
        + "\n"
        + "## Behavior\n"
        + "\n"
        + "See `requirements/`.\n"
        + "\n"
        + "## Interfaces\n"
        + "\n"
        + "See `interface/`.\n"
        + "\n"
        + "## Data\n"
        + "\n"
        + "See `interface/data/`.\n"
        + "\n"
        + "## Acceptance criteria\n"
        + "\n"
        + "See `acceptance/`.\n"
        + "\n"
        + "## Non-functional constraints\n"
        + "\n"
        + "See `constraints.md`.\n"
        + "\n"
        + "## Open questions\n"
        + "\n"
        + open_questions_body
        + "## Change log\n"
        + "\n"
        + "- Initial draft.\n"
    )


def _build_repo(repo_root, open_questions_body):
    specs = repo_root / "specs"
    _write(
        specs / "glossary.md",
        "# Glossary\n\n- **Foo thing** — a small thing foo does.\n",
    )
    comp = specs / "components" / "foo"
    _write(comp / "component.md", _component_md(open_questions_body))
    _write(
        comp / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n\n**R-FOO-001** — Foo MUST do the small thing.\n",
    )
    _write(
        comp / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n"
        + "\n"
        + "Covers: R-FOO-001\n"
        + "Kind: generated-test\n"
        + "\n"
        + "```gherkin\n"
        + "Given a foo\n"
        + "When it runs\n"
        + "Then it does the small thing\n"
        + "```\n",
    )
    _write(
        comp / "constraints.md",
        "# Constraints\n\nNone beyond the defaults.\n",
    )
    return comp / "component.md"


def _lint_002_fails(report):
    return [
        f
        for f in field(report, "findings")
        if field(f, "rule_id") == "R-LINT-002" and field(f, "severity") == "fail"
    ]


def test_ratified_with_nonempty_open_questions_fails_r_lint_002(tmp_path):
    repo_root = tmp_path / "repo"
    _build_repo(
        repo_root,
        "- Whether foo should also do a second thing.\n\n",
    )

    report = spec_linter.lint(None, repo_root)

    hits = _lint_002_fails(report)
    assert hits, "expected a fail-severity R-LINT-002 finding, got: " + repr(
        [(field(f, "rule_id"), field(f, "severity")) for f in field(report, "findings")]
    )
    assert any(
        str(field(f, "file")).replace("\\", "/").endswith("components/foo/component.md")
        for f in hits
    )
    assert report.hard_failures >= 1


def test_ratified_with_empty_open_questions_has_no_r_lint_002(tmp_path):
    repo_root = tmp_path / "repo"
    _build_repo(repo_root, "")

    report = spec_linter.lint(None, repo_root)

    assert _lint_002_fails(report) == []


def test_cli_reports_r_lint_002_and_exits_1(tmp_path, capsys):
    repo_root = tmp_path / "repo"
    _build_repo(
        repo_root,
        "- Whether foo should also do a second thing.\n\n",
    )

    code = spec_linter.main(["--format=json", "--repo-root=" + str(repo_root)])

    out = capsys.readouterr().out
    assert code == 1
    doc = json.loads(out)
    assert any(
        f["rule_id"] == "R-LINT-002" and f["severity"] == "fail"
        for f in doc["findings"]
    )
    assert doc["summary"]["hard_failures"] >= 1