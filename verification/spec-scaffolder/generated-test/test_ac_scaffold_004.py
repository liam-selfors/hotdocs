import os
import shutil
import subprocess
from pathlib import Path

import pytest

import spec_scaffolder


pytestmark = pytest.mark.skipif(
    shutil.which("git") is None, reason="git executable is required"
)


def _git_env():
    env = dict(os.environ)
    env.setdefault("GIT_AUTHOR_NAME", "Test Author")
    env.setdefault("GIT_AUTHOR_EMAIL", "test@example.invalid")
    env.setdefault("GIT_COMMITTER_NAME", "Test Author")
    env.setdefault("GIT_COMMITTER_EMAIL", "test@example.invalid")
    return env


def _git(repo_root, *args):
    result = subprocess.run(
        [
            "git",
            "-c", "user.name=Test Author",
            "-c", "user.email=test@example.invalid",
            "-c", "commit.gpgsign=false",
            *args,
        ],
        cwd=str(repo_root),
        env=_git_env(),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"git {args} failed: {result.stdout}\n{result.stderr}"
    )
    return result.stdout


def _init_repo(repo_root):
    (repo_root / "specs" / "decisions").mkdir(parents=True)
    _git(repo_root, "init", "-q")


def _commit_all(repo_root, message):
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-q", "-m", message)


def _lines(path):
    return path.read_text(encoding="utf-8").splitlines()


def _make_ratified_decision(repo_root, title, expected_id):
    written = spec_scaffolder.new_decision(repo_root, title)
    record = repo_root / "specs" / "decisions" / f"{expected_id}.md"
    assert record.is_file(), f"new_decision did not write {record} (got {written})"
    spec_scaffolder.ratify(repo_root, expected_id)
    assert "last_ratified_commit: PENDING-COMMIT" in _lines(record), (
        "precondition: ratified record should hold PENDING-COMMIT"
    )
    return record


def test_record_commit_uses_git_hash_then_refuses_second_time(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _init_repo(repo_root)

    record = _make_ratified_decision(repo_root, "First decision", "D1")
    _commit_all(repo_root, "add D1")

    expected = _git(
        repo_root, "log", "-1", "--format=%h", "--", "specs/decisions/D1.md"
    ).strip()
    assert expected

    result = spec_scaffolder.record_commit(repo_root, "D1")
    assert result == expected

    lines = _lines(record)
    assert f"last_ratified_commit: {expected}" in lines
    assert "last_ratified_commit: PENDING-COMMIT" not in lines

    before = record.read_bytes()
    with pytest.raises(LookupError):
        spec_scaffolder.record_commit(repo_root, "D1")
    assert record.read_bytes() == before


def test_record_commit_uncommitted_record_raises_then_explicit_commit_succeeds(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _init_repo(repo_root)

    # D1 exists and is committed so the repository has history.
    d1 = repo_root / "specs" / "decisions" / "D1.md"
    spec_scaffolder.new_decision(repo_root, "First decision")
    assert d1.is_file()
    _commit_all(repo_root, "add D1")

    # D2 is ratified but never committed.
    record = _make_ratified_decision(repo_root, "Second decision", "D2")

    before = record.read_bytes()
    with pytest.raises(LookupError):
        spec_scaffolder.record_commit(repo_root, "D2")
    assert record.read_bytes() == before

    result = spec_scaffolder.record_commit(repo_root, "D2", commit="abc1234")
    assert result == "abc1234"

    lines = _lines(record)
    assert "last_ratified_commit: abc1234" in lines
    assert "last_ratified_commit: PENDING-COMMIT" not in lines