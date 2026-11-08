import contextlib
import io
import json
import os
import subprocess

import pytest

import decision_drift_detector


def make_git_repo(path):
    subprocess.run(["git", "init"], cwd=path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=path, check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=path, check=True, capture_output=True,
    )
    (path / "specs").mkdir(parents=True, exist_ok=True)
    (path / "specs" / ".gitkeep").write_text("")
    subprocess.run(["git", "add", "-A"], cwd=path, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "init"], cwd=path, check=True, capture_output=True,
    )


def run_main(argv):
    stdout = io.StringIO()
    with contextlib.redirect_stdout(stdout):
        try:
            result = decision_drift_detector.main(argv)
        except SystemExit as e:
            if e.code is None:
                result = 0
            elif isinstance(e.code, int):
                result = e.code
            else:
                result = 1
    return result, stdout.getvalue()


def test_decision_drift_no_drift_json(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    make_git_repo(repo)

    argv = ["decision-drift", f"--repo-root={repo}", "--format=json"]
    exit_code, output = run_main(argv)

    assert exit_code == 0
    report = json.loads(output)
    entries = (
        report.get("entries") if isinstance(report, dict) else getattr(report, "entries", None)
    )
    assert entries == []


def test_decision_impact_human_readable(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    make_git_repo(repo)

    argv = ["decision-impact", "D1", f"--repo-root={repo}"]
    exit_code, output = run_main(argv)

    assert exit_code == 0
    assert output.strip() != ""
    with pytest.raises((json.JSONDecodeError, ValueError)):
        json.loads(output)


def test_decision_impact_missing_decision_id(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    make_git_repo(repo)

    argv = ["decision-impact", f"--repo-root={repo}"]
    exit_code, _output = run_main(argv)

    assert exit_code == 2


def test_decision_drift_not_a_git_repo(tmp_path):
    not_repo = tmp_path / "not_a_repo"
    not_repo.mkdir()

    argv = ["decision-drift", f"--repo-root={not_repo}"]
    exit_code, _output = run_main(argv)

    assert exit_code == 2


def test_decision_drift_default_repo_root(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    make_git_repo(repo)

    cwd = os.getcwd()
    os.chdir(repo)
    try:
        argv = ["decision-drift"]
        exit_code, _output = run_main(argv)
    finally:
        os.chdir(cwd)

    assert exit_code == 0


def test_decision_drift_bad_format(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    make_git_repo(repo)

    argv = ["decision-drift", f"--repo-root={repo}", "--format=bogus"]
    exit_code, _output = run_main(argv)

    assert exit_code == 2