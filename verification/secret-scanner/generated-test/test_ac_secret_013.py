# hotdocs-criterion: sha256:cc5669436e3d39430d3990d11809b5a161d06f62cda2b1c7cc7b7898c05456aa
import json
import os
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

import pytest

import secret_scanner


# Built by concatenation so this test file itself never holds the literal key.
PLANTED_KEY = "AKIA" + "ABCDEFGHIJKLMNOP"


FAKE_CACHE_MANAGER = '''\
import datetime
from dataclasses import dataclass


class SchemaValidationError(ValueError):
    pass


@dataclass
class CacheKey:
    spec_bundle_hash: str
    gate_inputs_hash: str
    gate_version: str
    model_pin: str


@dataclass
class CachedResult:
    gate_type: str
    payload: dict
    stored_at: str


class Miss:
    def __eq__(self, other):
        return isinstance(other, Miss)

    def __hash__(self):
        return 0


def get(cache_key, *, repo_root=None):
    return Miss()


def put(cache_key, result, *, repo_root=None):
    return None


def now_iso():
    now = datetime.datetime.now(datetime.timezone.utc)
    return now.strftime("%Y-%m-%dT%H:%M:%SZ")


def stats(*, repo_root=None):
    return {"entry_count": 0}


def main(argv=None):
    return 0
'''


class _FakeResponse:
    status = 200

    def read(self, *args, **kwargs):
        return b""

    def getcode(self):
        return 200

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _fake_urlopen(*args, **kwargs):
    return _FakeResponse()


@pytest.fixture(autouse=True)
def _isolate(monkeypatch):
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    for name in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen)
    monkeypatch.setattr(sys, "dont_write_bytecode", True)


def _make_repo(base: Path) -> Path:
    repo_root = base / "repo"
    (repo_root / "gen" / "cache-manager").mkdir(parents=True)
    (repo_root / "gen" / "cache-manager" / "cache_manager.py").write_text(
        FAKE_CACHE_MANAGER, encoding="utf-8"
    )
    (repo_root / "gen" / "foo").mkdir(parents=True)
    (repo_root / "gen" / "foo" / "a.py").write_text("X = 1\n", encoding="utf-8")
    return repo_root


def _field(value, name):
    return value.get(name) if isinstance(value, dict) else getattr(value, name, None)


def test_full_scan_clean_json_returns_0_and_not_flagged(tmp_path, monkeypatch, capsys):
    repo_root = _make_repo(tmp_path)
    monkeypatch.chdir(repo_root)
    capsys.readouterr()

    code = secret_scanner.main([f"--repo-root={repo_root}", "--format=json"])
    out = capsys.readouterr().out

    assert code == 0, out
    payload = json.loads(out.strip())
    assert _field(payload, "flagged") is False


def test_full_scan_flagged_text_returns_1_and_prints_flagged(tmp_path, monkeypatch, capsys):
    repo_root = _make_repo(tmp_path)
    (repo_root / "gen" / "foo" / "c.py").write_text(
        f'K = "{PLANTED_KEY}"\n', encoding="utf-8"
    )
    monkeypatch.chdir(repo_root)
    capsys.readouterr()

    code = secret_scanner.main(
        ["--repo-root", str(repo_root), "--format", "text"]
    )
    out = capsys.readouterr().out

    assert code == 1, out
    assert "FLAGGED" in out


def test_precommit_repeatable_files(tmp_path, monkeypatch, capsys):
    repo_root = _make_repo(tmp_path)
    clean = repo_root / "gen" / "foo" / "clean.py"
    clean.write_text("Y = 2\n", encoding="utf-8")
    dirty = repo_root / "gen" / "foo" / "c.py"
    dirty.write_text(f'K = "{PLANTED_KEY}"\n', encoding="utf-8")
    monkeypatch.chdir(repo_root)
    capsys.readouterr()

    first = secret_scanner.main(
        ["precommit", "--files", str(clean), f"--files={dirty}"]
    )
    first_out = capsys.readouterr().out
    assert first == 1, first_out

    second = secret_scanner.main(["precommit", f"--files={clean}"])
    second_out = capsys.readouterr().out
    assert second == 0, second_out


def _git(repo_root: Path, *args: str) -> None:
    subprocess.run(
        [
            "git",
            "-c", "user.name=ac-test",
            "-c", "user.email=ac-test@example.invalid",
            "-c", "commit.gpgsign=false",
            "-c", "core.hooksPath=/dev/null",
            *args,
        ],
        cwd=str(repo_root),
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


@pytest.mark.skipif(shutil.which("git") is None, reason="git not available")
def test_precommit_default_files_from_git_staged(tmp_path, monkeypatch, capsys):
    repo_root = tmp_path / "gitrepo"
    repo_root.mkdir()
    _git(repo_root, "init", "-q")
    (repo_root / "clean.py").write_text("Z = 3\n", encoding="utf-8")
    _git(repo_root, "add", "clean.py")
    _git(repo_root, "commit", "-q", "--no-verify", "-m", "init")

    staged = repo_root / "staged.py"
    staged.write_text(f'K = "{PLANTED_KEY}"\n', encoding="utf-8")
    _git(repo_root, "add", "staged.py")

    monkeypatch.chdir(repo_root)
    capsys.readouterr()

    code = secret_scanner.main(["precommit", "--repo-root", str(repo_root)])
    out = capsys.readouterr().out
    assert code == 1, out


@pytest.mark.parametrize(
    "argv_builder",
    [
        lambda root: [f"--repo-root={root}", "--format=bogus"],
        lambda root: [f"--repo-root={root}", "--no-such-flag"],
        lambda root: ["no-such-subcommand", f"--repo-root={root}"],
        lambda root: ["--repo-root"],
        lambda root: ["propose", "--format=json"],
    ],
    ids=[
        "invalid-format",
        "unknown-argument",
        "unknown-subcommand",
        "repo-root-last-without-value",
        "propose-with-format",
    ],
)
def test_usage_errors_return_2(tmp_path, monkeypatch, capsys, argv_builder):
    repo_root = _make_repo(tmp_path)
    monkeypatch.chdir(repo_root)
    capsys.readouterr()

    code = secret_scanner.main(argv_builder(str(repo_root)))
    captured = capsys.readouterr()
    assert code == 2, (captured.out, captured.err)