import json
from pathlib import Path

import pytest

import spec_linter


def _get(value, name, default=None):
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _findings(report):
    findings = _get(report, "findings")
    assert findings is not None, "LintReport must expose findings"
    return list(findings)


def _hard_failures(report):
    if isinstance(report, dict):
        if "hard_failures" in report:
            return report["hard_failures"]
        summary = report.get("summary") or {}
        return summary.get("hard_failures")
    value = getattr(report, "hard_failures", None)
    if value is None:
        summary = getattr(report, "summary", None)
        if summary is not None:
            value = _get(summary, "hard_failures")
    return value


def _norm(path_value):
    return str(path_value).replace("\\", "/")


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _var_doc(var_id, sensitivity, extra_bullets):
    lines = [
        "---",
        f"id: {var_id}",
        f"title: {var_id} declaration",
        "status: draft",
        "owners: [alice]",
        "---",
        "",
        f"# {var_id}",
        "",
        f"- name: {var_id}",
        "- required",
        "- type: string",
        "- description: A test configuration parameter.",
        f"- sensitivity: {sensitivity}",
    ]
    lines.extend(extra_bullets)
    lines.append("")
    return "\n".join(lines)


def _make_repo(tmp_path: Path, var_id, sensitivity, extra_bullets):
    repo_root = tmp_path / "repo"
    (repo_root / "specs").mkdir(parents=True, exist_ok=True)
    _write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Widget** — a test term.\n",
    )
    rel = f"specs/vars/{var_id}.md"
    _write(repo_root / rel, _var_doc(var_id, sensitivity, extra_bullets))
    return repo_root, rel


def _lint013_findings_for(report, rel):
    out = []
    for f in _findings(report):
        if _get(f, "rule_id") != "R-LINT-013":
            continue
        file_value = _get(f, "file")
        if file_value is not None and _norm(file_value).endswith(rel):
            out.append(f)
    return out


def test_secret_var_with_default_fails_r_lint_013(tmp_path):
    repo_root, rel = _make_repo(
        tmp_path, "VAR-SECRET-TOKEN", "secret", ["- default: hunter2"]
    )
    report = spec_linter.lint(None, repo_root)

    matches = _lint013_findings_for(report, rel)
    assert matches, (
        "expected an R-LINT-013 finding on the secret var with a default; got "
        + repr([(_get(f, "rule_id"), _get(f, "file")) for f in _findings(report)])
    )
    for f in matches:
        assert _get(f, "severity") == "fail"
        line = _get(f, "line")
        assert isinstance(line, int)
        assert line >= 1
        message = _get(f, "message")
        assert isinstance(message, str) and message.strip()

    hard = _hard_failures(report)
    assert hard is not None and hard >= 1


def test_secret_var_with_example_also_fails_r_lint_013(tmp_path):
    repo_root, rel = _make_repo(
        tmp_path, "VAR-SECRET-KEY", "secret", ["- example: sk-test-123"]
    )
    report = spec_linter.lint(None, repo_root)
    matches = _lint013_findings_for(report, rel)
    assert matches
    assert all(_get(f, "severity") == "fail" for f in matches)


def test_secret_var_without_default_or_example_has_no_r_lint_013(tmp_path):
    repo_root, rel = _make_repo(tmp_path, "VAR-SECRET-PLAIN", "secret", [])
    report = spec_linter.lint(None, repo_root)
    assert not _lint013_findings_for(report, rel)
    assert not [f for f in _findings(report) if _get(f, "rule_id") == "R-LINT-013"]


def test_non_secret_var_with_default_has_no_r_lint_013(tmp_path):
    repo_root, rel = _make_repo(
        tmp_path, "VAR-PUBLIC-URL", "non-secret", ["- default: http://localhost"]
    )
    report = spec_linter.lint(None, repo_root)
    assert not _lint013_findings_for(report, rel)
    assert not [f for f in _findings(report) if _get(f, "rule_id") == "R-LINT-013"]


def test_cli_reports_r_lint_013_and_exits_1(tmp_path, capsys):
    repo_root, rel = _make_repo(
        tmp_path, "VAR-SECRET-TOKEN", "secret", ["- default: hunter2"]
    )
    code = spec_linter.main(["--format=json", f"--repo-root={repo_root}"])
    assert code == 1
    out = capsys.readouterr().out
    assert "R-LINT-013" in out
    try:
        data = json.loads(out)
    except ValueError:
        data = None
    if isinstance(data, dict):
        found = [
            f
            for f in data.get("findings", [])
            if f.get("rule_id") == "R-LINT-013"
            and _norm(f.get("file", "")).endswith(rel)
        ]
        assert found
        assert all(f.get("severity") == "fail" for f in found)
        assert data.get("summary", {}).get("hard_failures", 0) >= 1