# hotdocs-criterion: sha256:960633d23ca2c4c3539bd33f5312a6f7dd47fd7c5644c0224110e694f761f5fb
import shutil
import subprocess
from pathlib import Path

import pytest

import spec_scaffolder


pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")


def _git(repo_root, *args):
    result = subprocess.run(
        [
            "git",
            "-c", "user.name=Test",
            "-c", "user.email=test@example.com",
            "-c", "commit.gpgsign=false",
            *args,
        ],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def _init_repo(tmp_path):
    repo_root = tmp_path / "repo"
    (repo_root / "specs" / "decisions").mkdir(parents=True)
    _git(repo_root, "init", "-q")
    return repo_root


def _resolve(repo_root, path):
    path = Path(path)
    return path if path.is_absolute() else repo_root / path


def _new_ratified(repo_root, title):
    path = _resolve(repo_root, spec_scaffolder.new_decision(repo_root, title))
    decision_id = path.stem
    spec_scaffolder.ratify(repo_root, decision_id)
    return decision_id, path


def _lines(path):
    return [line.rstrip("\r") for line in path.read_text().splitlines()]


def test_record_commit_uses_git_hash_then_refuses_second_call(tmp_path):
    repo_root = _init_repo(tmp_path)
    decision_id, d1 = _new_ratified(repo_root, "First decision")
    assert decision_id == "D1"
    assert d1 == repo_root / "specs" / "decisions" / "D1.md"
    assert d1.is_file()

    _git(repo_root, "add", "specs/decisions/D1.md")
    _git(repo_root, "commit", "-q", "-m", "add D1")

    expected = _git(
        repo_root, "log", "-1", "--format=%h", "--", "specs/decisions/D1.md"
    ).strip()
    assert expected

    returned = spec_scaffolder.record_commit(repo_root, "D1")
    assert returned == expected
    assert ("last_ratified_commit: " + expected) in _lines(d1)
    assert "last_ratified_commit: PENDING-COMMIT" not in _lines(d1)

    before = d1.read_bytes()
    with pytest.raises(LookupError):
        spec_scaffolder.record_commit(repo_root, "D1")
    assert d1.read_bytes() == before


def test_record_commit_uncommitted_raises_and_explicit_commit_records(tmp_path):
    repo_root = _init_repo(tmp_path)

    # An initial commit so the repository has history, but not of D2.
    d1_id, d1 = _new_ratified(repo_root, "First decision")
    assert d1_id == "D1"
    _git(repo_root, "add", "specs/decisions/D1.md")
    _git(repo_root, "commit", "-q", "-m", "add D1")

    d2_id, d2 = _new_ratified(repo_root, "Second decision")
    assert d2_id == "D2"
    assert d2.is_file()

    before = d2.read_bytes()
    with pytest.raises(LookupError):
        spec_scaffolder.record_commit(repo_root, "D2")
    assert d2.read_bytes() == before

    returned = spec_scaffolder.record_commit(repo_root, "D2", commit="abc1234")
    assert returned == "abc1234"
    assert "last_ratified_commit: abc1234" in _lines(d2)
    assert "last_ratified_commit: PENDING-COMMIT" not in _lines(d2)