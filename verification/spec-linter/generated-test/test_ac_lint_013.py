# hotdocs-criterion: sha256:4fed220facd32d923d3756fb381907d2c25560400e2567523770ab79c99b945b
"""AC-LINT-013: a specs/vars/ declaration with `sensitivity: secret` that
carries a `default` field yields a fail-severity R-LINT-013 finding."""

import json
from pathlib import Path

import spec_linter


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


VAR_ID = "VAR-DB-PASSWORD"
VAR_FILE = "VAR-DB-PASSWORD.md"


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_corpus(repo_root, with_default):
    specs = repo_root / "specs"
    _write(
        specs / "glossary.md",
        "# Glossary\n"
        "\n"
        "- **Widget** \u2014 a placeholder term for this fixture.\n",
    )
    body_lines = [
        "---",
        "id: " + VAR_ID,
        "title: Database password",
        "status: draft",
        "owners: [pipeline-team]",
        "---",
        "",
        "# " + VAR_ID,
        "",
        "- required",
        "- type: secret-ref",
        "- description: Password used to connect to the database.",
        "- sensitivity: secret",
    ]
    if with_default:
        body_lines.append("- default: hunter2")
    body_lines.append("")
    _write(specs / "vars" / VAR_FILE, "\n".join(body_lines))


def _findings(report):
    return list(field(report, "findings"))


def _r013_findings(report):
    return [f for f in _findings(report) if field(f, "rule_id") == "R-LINT-013"]


def test_secret_var_with_default_fails_r_lint_013(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_corpus(repo_root, with_default=True)

    report = spec_linter.lint(None, repo_root)

    r013 = _r013_findings(report)
    assert r013, "expected an R-LINT-013 finding, got: " + repr(_findings(report))
    fails = [f for f in r013 if field(f, "severity") == "fail"]
    assert fails, "expected R-LINT-013 to be fail severity, got: " + repr(r013)
    assert any(
        str(field(f, "file")).replace("\\", "/").endswith("specs/vars/" + VAR_FILE)
        for f in fails
    ), "expected the finding on the var declaration, got: " + repr(fails)
    assert field(report, "hard_failures") >= 1


def test_secret_var_without_default_has_no_r_lint_013(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_corpus(repo_root, with_default=False)

    report = spec_linter.lint(None, repo_root)

    assert _r013_findings(report) == [], repr(_r013_findings(report))


def test_cli_reports_r_lint_013_fail_and_exit_1(tmp_path, capsys):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_corpus(repo_root, with_default=True)

    code = spec_linter.main(["--repo-root=" + str(repo_root), "--format=json"])
    out = capsys.readouterr().out

    assert code == 1
    doc = json.loads(out)
    r013 = [f for f in doc["findings"] if f["rule_id"] == "R-LINT-013"]
    assert any(f["severity"] == "fail" for f in r013), repr(doc["findings"])
    assert doc["summary"]["hard_failures"] >= 1