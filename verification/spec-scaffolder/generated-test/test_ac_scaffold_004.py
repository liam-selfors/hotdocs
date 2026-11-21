# hotdocs-criterion: sha256:396452000b6199fd3d7b6d9d5cac01e633bc4c1c3e5bba3051222e0b9a47a1d3
import os
import shutil
import subprocess
from pathlib import Path

import pytest

import spec_scaffolder


pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git not available")


def _git_env():
    env = dict(os.environ)
    env["GIT_AUTHOR_NAME"] = "Test Author"
    env["GIT_AUTHOR_EMAIL"] = "test@example.invalid"
    env["GIT_COMMITTER_NAME"] = "Test Author"
    env["GIT_COMMITTER_EMAIL"] = "test@example.invalid"
    env.pop("GIT_DIR", None)
    env.pop("GIT_WORK_TREE", None)
    return env


def _git(repo_root, *args):
    result = subprocess.run(
        ["git", *args],
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
    (repo_root / "README.md").write_text("fixture\n")
    _git(repo_root, "add", "README.md")
    _git(repo_root, "commit", "-q", "-m", "initial")


def _make_ratified(repo_root, title):
    path = Path(spec_scaffolder.new_decision(repo_root, title))
    decision_id = path.stem
    spec_scaffolder.ratify(repo_root, decision_id)
    return decision_id, path


def _commit_file(repo_root, rel):
    _git(repo_root, "add", rel)
    _git(repo_root, "commit", "-q", "-m", "add " + rel)


def _lines(path):
    return path.read_text().splitlines()


def test_record_commit_from_git_then_refuses_second_time(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _init_repo(repo_root)

    decision_id, _ = _make_ratified(repo_root, "First decision")
    assert decision_id == "D1"
    record = repo_root / "specs" / "decisions" / "D1.md"
    assert record.is_file()
    assert "last_ratified_commit: PENDING-COMMIT" in _lines(record)

    _commit_file(repo_root, "specs/decisions/D1.md")
    expected = _git(
        repo_root, "log", "-1", "--format=%h", "--", "specs/decisions/D1.md"
    ).strip()
    assert expected

    returned = spec_scaffolder.record_commit(repo_root, "D1")
    assert returned == expected
    lines = _lines(record)
    assert ("last_ratified_commit: " + expected) in lines
    assert "last_ratified_commit: PENDING-COMMIT" not in lines

    before = record.read_bytes()
    with pytest.raises(LookupError):
        spec_scaffolder.record_commit(repo_root, "D1")
    assert record.read_bytes() == before


def test_record_commit_uncommitted_raises_then_explicit_commit(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _init_repo(repo_root)

    d1, _ = _make_ratified(repo_root, "First decision")
    assert d1 == "D1"
    _commit_file(repo_root, "specs/decisions/D1.md")

    d2, _ = _make_ratified(repo_root, "Second decision")
    assert d2 == "D2"
    record = repo_root / "specs" / "decisions" / "D2.md"
    assert record.is_file()
    assert "last_ratified_commit: PENDING-COMMIT" in _lines(record)

    before = record.read_bytes()
    with pytest.raises(LookupError):
        spec_scaffolder.record_commit(repo_root, "D2")
    assert record.read_bytes() == before

    returned = spec_scaffolder.record_commit(repo_root, "D2", commit="abc1234")
    assert returned == "abc1234"
    lines = _lines(record)
    assert "last_ratified_commit: abc1234" in lines
    assert "last_ratified_commit: PENDING-COMMIT" not in lines