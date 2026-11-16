"""AC-LINT-013 (Covers: R-LINT-013).

Given a specs/vars/ declaration with sensitivity: secret and a default field
present, when hotdocs lint runs against it, then the report contains a
fail-severity finding for rule R-LINT-013.
"""

import json
from pathlib import Path

import spec_linter


VAR_ID = "VAR-TEST-SECRET"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _findings(report):
    return list(field(report, "findings"))


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _make_repo(root: Path, body_bullets: str, var_id: str = VAR_ID) -> Path:
    """Build a minimal synthetic corpus holding one var declaration."""
    _write(
        root / "specs" / "glossary.md",
        "# Glossary\n\n- **Widget** — a test term.\n",
    )
    var_path = root / "specs" / "vars" / f"{var_id}.md"
    _write(
        var_path,
        "---\n"
        f"id: {var_id}\n"
        "title: Test secret variable\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "---\n"
        "\n"
        f"# {var_id}\n"
        "\n"
        f"{body_bullets}",
    )
    return var_path


SECRET_WITH_DEFAULT = (
    "- name: TEST_SECRET\n"
    "- required\n"
    "- type: secret-ref\n"
    "- description: A test secret reference.\n"
    "- sensitivity: secret\n"
    "- default: hunter2\n"
)

SECRET_WITHOUT_DEFAULT = (
    "- name: TEST_SECRET\n"
    "- required\n"
    "- type: secret-ref\n"
    "- description: A test secret reference.\n"
    "- sensitivity: secret\n"
)


def _lint013(findings):
    return [f for f in findings if field(f, "rule_id") == "R-LINT-013"]


def test_secret_var_with_default_fails_r_lint_013(tmp_path):
    _make_repo(tmp_path, SECRET_WITH_DEFAULT)

    report = spec_linter.lint(None, tmp_path)

    hits = _lint013(_findings(report))
    assert hits, (
        "expected an R-LINT-013 finding, got: "
        + repr([(field(f, "rule_id"), field(f, "message")) for f in _findings(report)])
    )
    fail_hits = [f for f in hits if field(f, "severity") == "fail"]
    assert fail_hits, f"R-LINT-013 finding(s) not fail severity: {hits!r}"
    assert any(VAR_ID in str(field(f, "file")) for f in fail_hits)

    hard = report["hard_failures"] if isinstance(report, dict) else report.hard_failures
    assert hard >= 1


def test_secret_var_without_default_has_no_r_lint_013(tmp_path):
    _make_repo(tmp_path, SECRET_WITHOUT_DEFAULT)

    report = spec_linter.lint(None, tmp_path)

    assert _lint013(_findings(report)) == []


def test_cli_reports_r_lint_013_and_exits_1(tmp_path, capsys):
    _make_repo(tmp_path, SECRET_WITH_DEFAULT)

    code = spec_linter.main(["--format=json", f"--repo-root={tmp_path}"])
    out = capsys.readouterr().out

    assert code == 1
    doc = json.loads(out)
    hits = [
        f
        for f in doc["findings"]
        if f["rule_id"] == "R-LINT-013" and f["severity"] == "fail"
    ]
    assert hits, f"no fail-severity R-LINT-013 finding in CLI output: {doc!r}"
    assert doc["summary"]["hard_failures"] >= 1