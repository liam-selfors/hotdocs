"""AC-LINT-006: a non-sealed component with zero `realizes` entries fails lint.

Covers: R-LINT-006
"""

import json
from pathlib import Path

import pytest

import spec_linter


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _sev(value):
    sev = field(value, "severity")
    return str(getattr(sev, "value", sev))


def _findings(report):
    return list(field(report, "findings"))


def _rule_findings(report, rule_id):
    return [f for f in _findings(report) if field(f, "rule_id") == rule_id]


BODY = """
# Foo

## Purpose

Foo does one small thing for testing purposes.

## Scope

- In scope: the one small thing.
- Out of scope: everything else.

## Definitions

None.

## Behavior

See `requirements/`.

## Interfaces

See `interface/`.

## Data

See `interface/data/`.

## Acceptance criteria

See `acceptance/`.

## Non-functional constraints

See `constraints.md`.

## Open questions

## Change log

- Initial draft.
"""


def _write_component(repo_root: Path, extra_frontmatter: str = "") -> Path:
    comp_dir = repo_root / "specs" / "components" / "foo"
    (comp_dir / "requirements").mkdir(parents=True)
    (comp_dir / "acceptance").mkdir(parents=True)
    (comp_dir / "interface").mkdir(parents=True)
    fm = (
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [test-team]\n"
        + extra_frontmatter
        + "---\n"
    )
    path = comp_dir / "component.md"
    path.write_text(fm + BODY, encoding="utf-8")
    (comp_dir / "requirements" / "R-FOO-001.md").write_text(
        "# R-FOO-001\n\n**R-FOO-001** — Foo MUST do the one small thing.\n",
        encoding="utf-8",
    )
    (comp_dir / "acceptance" / "AC-FOO-001.md").write_text(
        "# AC-FOO-001\n\nCovers: R-FOO-001\nKind: generated-test\n\n"
        "```gherkin\nGiven foo\nWhen it runs\nThen it does the thing\n```\n",
        encoding="utf-8",
    )
    (comp_dir / "constraints.md").write_text(
        "# Constraints\n\nNone.\n", encoding="utf-8"
    )
    return path


def _write_product(repo_root: Path) -> None:
    prod = repo_root / "specs" / "product"
    prod.mkdir(parents=True, exist_ok=True)
    (prod / "foo-capability.md").write_text(
        "---\n"
        "id: P-FOO\n"
        "title: Foo capability\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "---\n\n"
        "# Foo capability\n\n## Purpose\n\nDo foo.\n\n## Scope\n\n- foo\n",
        encoding="utf-8",
    )


def _assert_r_lint_006_fail(report):
    hits = _rule_findings(report, "R-LINT-006")
    fails = [f for f in hits if _sev(f) == "fail"]
    assert fails, (
        "expected a fail-severity R-LINT-006 finding, got: "
        + repr([(field(f, "rule_id"), _sev(f), field(f, "file")) for f in _findings(report)])
    )
    files = [str(field(f, "file")).replace("\\", "/") for f in fails]
    assert any(p.endswith("components/foo/component.md") for p in files), files
    assert field(report, "hard_failures") >= 1


def test_sealed_absent_and_no_realizes_fails(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write_component(repo_root)
    report = spec_linter.lint(None, repo_root)
    _assert_r_lint_006_fail(report)


def test_sealed_false_and_no_realizes_fails(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write_component(repo_root, "sealed: false\n")
    report = spec_linter.lint(None, repo_root)
    _assert_r_lint_006_fail(report)


def test_non_sealed_with_realizes_has_no_r_lint_006(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write_product(repo_root)
    _write_component(repo_root, "realizes: [P-FOO]\n")
    report = spec_linter.lint(None, repo_root)
    assert not [
        f for f in _rule_findings(report, "R-LINT-006") if _sev(f) == "fail"
    ]


def test_sealed_true_without_realizes_has_no_r_lint_006(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write_component(repo_root, "sealed: true\nsource_path: legacy/foo/\n")
    report = spec_linter.lint(None, repo_root)
    assert not [
        f for f in _rule_findings(report, "R-LINT-006") if _sev(f) == "fail"
    ]


def test_cli_reports_r_lint_006_and_exits_1(tmp_path, capsys):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write_component(repo_root)
    code = spec_linter.main(["--format=json", f"--repo-root={repo_root}"])
    out = capsys.readouterr().out
    assert code == 1
    doc = json.loads(out)
    hits = [
        f
        for f in doc["findings"]
        if f["rule_id"] == "R-LINT-006" and f["severity"] == "fail"
    ]
    assert hits, doc
    assert doc["summary"]["hard_failures"] >= 1