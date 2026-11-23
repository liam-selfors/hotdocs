# hotdocs-criterion: sha256:081f6202293f6236e6edbdcc659c7ed3cb0c7dbcad036689ac70523ef1bd681a
import os
import subprocess
from pathlib import Path

import pytest

import spec_scaffolder


def _git_env():
    env = dict(os.environ)
    env["GIT_AUTHOR_NAME"] = "Test Author"
    env["GIT_AUTHOR_EMAIL"] = "test@example.invalid"
    env["GIT_COMMITTER_NAME"] = "Test Author"
    env["GIT_COMMITTER_EMAIL"] = "test@example.invalid"
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    return env


def _git(repo_root, *args):
    result = subprocess.run(
        ["git", "-c", "commit.gpgsign=false", *args],
        cwd=str(repo_root),
        env=_git_env(),
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def _init_repo(repo_root):
    (repo_root / "specs" / "decisions").mkdir(parents=True)
    _git(repo_root, "init", "-q")
    _git(repo_root, "config", "user.name", "Test Author")
    _git(repo_root, "config", "user.email", "test@example.invalid")
    _git(repo_root, "config", "commit.gpgsign", "false")


def _new_ratified(repo_root, title):
    path = spec_scaffolder.new_decision(repo_root, title)
    decision_id = Path(path).stem
    spec_scaffolder.ratify(repo_root, decision_id)
    record = repo_root / "specs" / "decisions" / (decision_id + ".md")
    assert record.is_file()
    return decision_id, record


def _commit_all(repo_root, message):
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-q", "-m", message)


def _lines(path):
    return [line.rstrip("\r") for line in path.read_text().splitlines()]


def test_record_commit_from_git_then_refuses_second_call(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _init_repo(repo_root)

    decision_id, record = _new_ratified(repo_root, "First decision")
    assert decision_id == "D1"
    _commit_all(repo_root, "ratify D1")

    expected = _git(
        repo_root, "log", "-1", "--format=%h", "--", "specs/decisions/D1.md"
    ).strip()
    assert expected

    result = spec_scaffolder.record_commit(repo_root, "D1")
    assert result == expected
    lines = _lines(record)
    assert ("last_ratified_commit: " + expected) in lines
    assert "last_ratified_commit: PENDING-COMMIT" not in lines

    before = record.read_bytes()
    with pytest.raises(LookupError):
        spec_scaffolder.record_commit(repo_root, "D1")
    assert record.read_bytes() == before


def test_record_commit_uncommitted_requires_explicit_commit(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _init_repo(repo_root)

    first_id, _ = _new_ratified(repo_root, "First decision")
    _commit_all(repo_root, "ratify " + first_id)

    decision_id, record = _new_ratified(repo_root, "Second decision")
    assert decision_id == "D2"

    before = record.read_bytes()
    with pytest.raises(LookupError):
        spec_scaffolder.record_commit(repo_root, "D2")
    assert record.read_bytes() == before

    result = spec_scaffolder.record_commit(repo_root, "D2", commit="abc1234")
    assert result == "abc1234"
    lines = _lines(record)
    assert "last_ratified_commit: abc1234" in lines
    assert "last_ratified_commit: PENDING-COMMIT" not in lines