# hotdocs-criterion: sha256:3fe01d4ec487bf9cdb47a3f9c9f714abe31d31cb9df8d056106e8e661cfe6477
import os
import shutil
import subprocess
from pathlib import Path

import pytest

import spec_scaffolder


pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git is not installed")


def _git_env():
    env = dict(os.environ)
    env["GIT_AUTHOR_NAME"] = "test"
    env["GIT_AUTHOR_EMAIL"] = "test@example.com"
    env["GIT_COMMITTER_NAME"] = "test"
    env["GIT_COMMITTER_EMAIL"] = "test@example.com"
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env.pop("GIT_DIR", None)
    env.pop("GIT_WORK_TREE", None)
    return env


def _git(repo_root, *args):
    result = subprocess.run(
        ["git", "-c", "commit.gpgsign=false", "-c", "init.defaultBranch=main", *args],
        cwd=str(repo_root),
        env=_git_env(),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout


def _init_repo(tmp_path):
    repo_root = tmp_path / "repo"
    (repo_root / "specs" / "decisions").mkdir(parents=True)
    _git(repo_root, "init", "-q")
    (repo_root / "README.md").write_text("fixture\n", encoding="utf-8")
    _git(repo_root, "add", "README.md")
    _git(repo_root, "commit", "-q", "-m", "initial")
    return repo_root


def _make_ratified(repo_root, title):
    path = Path(spec_scaffolder.new_decision(repo_root, title))
    spec_scaffolder.ratify(repo_root, path.stem)
    return path


def _lines(path):
    return path.read_text(encoding="utf-8").splitlines()


def test_record_commit_uses_git_log_then_refuses_second_time(tmp_path):
    repo_root = _init_repo(tmp_path)
    d1 = _make_ratified(repo_root, "First decision")
    assert d1.name == "D1.md"
    d1_abs = d1 if d1.is_absolute() else repo_root / d1
    assert "last_ratified_commit: PENDING-COMMIT" in _lines(d1_abs)

    _git(repo_root, "add", "specs/decisions/D1.md")
    _git(repo_root, "commit", "-q", "-m", "ratify D1")

    expected = _git(repo_root, "log", "-1", "--format=%h", "--", "specs/decisions/D1.md").strip()
    assert expected

    returned = spec_scaffolder.record_commit(repo_root, "D1")
    assert returned == expected

    lines = _lines(d1_abs)
    assert ("last_ratified_commit: " + expected) in lines
    assert "last_ratified_commit: PENDING-COMMIT" not in lines

    before = d1_abs.read_bytes()
    with pytest.raises(LookupError):
        spec_scaffolder.record_commit(repo_root, "D1")
    assert d1_abs.read_bytes() == before


def test_record_commit_uncommitted_record_and_explicit_commit(tmp_path):
    repo_root = _init_repo(tmp_path)
    d1 = _make_ratified(repo_root, "First decision")
    assert d1.name == "D1.md"
    _git(repo_root, "add", "specs/decisions/D1.md")
    _git(repo_root, "commit", "-q", "-m", "ratify D1")

    d2 = _make_ratified(repo_root, "Second decision")
    assert d2.name == "D2.md"
    d2_abs = d2 if d2.is_absolute() else repo_root / d2
    assert "last_ratified_commit: PENDING-COMMIT" in _lines(d2_abs)

    before = d2_abs.read_bytes()
    with pytest.raises(LookupError):
        spec_scaffolder.record_commit(repo_root, "D2")
    assert d2_abs.read_bytes() == before

    returned = spec_scaffolder.record_commit(repo_root, "D2", commit="abc1234")
    assert returned == "abc1234"
    lines = _lines(d2_abs)
    assert "last_ratified_commit: abc1234" in lines
    assert "last_ratified_commit: PENDING-COMMIT" not in lines