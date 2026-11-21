# hotdocs-criterion: sha256:49839daf1a2a3b5abb456f3d44f5e04bd1fa1a6e6e130acaf37ea00d7d9c61fe
import json
import subprocess
from pathlib import Path

import decision_drift_detector


GIT_FLAGS = ["-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false"]


def git(repo_root, *args):
    return subprocess.run(
        ["git"] + GIT_FLAGS + list(args),
        cwd=str(repo_root),
        check=True,
        capture_output=True,
        text=True,
    )


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def make_clean_repo(repo_root):
    repo_root.mkdir(parents=True, exist_ok=True)
    git(repo_root, "init", "-q")
    write(
        repo_root / "specs" / "decisions" / "D1.md",
        "---\n"
        + "id: D1\n"
        + "title: First decision\n"
        + "status: draft\n"
        + "owners: [pipeline-team]\n"
        + "---\n"
        + "\n"
        + "# D1\n",
    )
    git(repo_root, "add", "-A")
    git(repo_root, "commit", "-q", "-m", "initial")
    return repo_root


def test_decision_drift_json_clean_repo_returns_0_with_empty_entries(tmp_path, capsys):
    repo = make_clean_repo(tmp_path / "repo")
    rc = decision_drift_detector.main(
        ["decision-drift", "--repo-root=" + str(repo), "--format=json"]
    )
    captured = capsys.readouterr()
    assert rc == 0, captured.err
    report = json.loads(captured.out)
    assert isinstance(report, dict)
    assert "entries" in report
    assert report["entries"] == []


def test_decision_impact_text_returns_0_and_prints_report(tmp_path, capsys):
    repo = make_clean_repo(tmp_path / "repo")
    rc = decision_drift_detector.main(
        ["decision-impact", "D1", "--repo-root=" + str(repo)]
    )
    captured = capsys.readouterr()
    assert rc == 0, captured.err
    assert captured.out.strip() != ""


def test_decision_impact_missing_decision_id_returns_2(tmp_path, capsys):
    repo = make_clean_repo(tmp_path / "repo")
    rc = decision_drift_detector.main(
        ["decision-impact", "--repo-root=" + str(repo)]
    )
    captured = capsys.readouterr()
    assert rc == 2
    assert "Traceback" not in captured.err


def test_decision_drift_not_a_git_repo_returns_2(tmp_path, capsys):
    not_git = tmp_path / "not-a-repo"
    not_git.mkdir()
    rc = decision_drift_detector.main(
        ["decision-drift", "--repo-root=" + str(not_git)]
    )
    captured = capsys.readouterr()
    assert rc == 2
    assert "Traceback" not in captured.err


def test_decision_drift_defaults_repo_root_to_cwd_git_root(tmp_path, capsys, monkeypatch):
    repo = make_clean_repo(tmp_path / "repo")
    monkeypatch.chdir(repo)
    rc = decision_drift_detector.main(["decision-drift"])
    captured = capsys.readouterr()
    assert rc == 0, captured.err


def test_decision_drift_bogus_format_returns_2(tmp_path, capsys):
    repo = make_clean_repo(tmp_path / "repo")
    rc = decision_drift_detector.main(
        ["decision-drift", "--repo-root=" + str(repo), "--format=bogus"]
    )
    captured = capsys.readouterr()
    assert rc == 2
    assert "Traceback" not in captured.err