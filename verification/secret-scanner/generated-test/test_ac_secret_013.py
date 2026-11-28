# hotdocs-criterion: sha256:df42aa863e48668eaddbc020b36a511dd2690001924a43d60e3ad5aee9f8002a
"""AC-SECRET-013: main(argv) implements interface/cli.md (R-SECRET-011)."""

import json
import shutil
import subprocess
import urllib.request
from pathlib import Path

import pytest

import secret_scanner


# Built by concatenation so this test file holds no contiguous key literal.
AWS_KEY = "AKIA" + "ABCDEFGHIJKLMNOP"

FAKE_CACHE_MANAGER = (
    "import dataclasses\n"
    "import time\n"
    "\n"
    "\n"
    "@dataclasses.dataclass\n"
    "class CacheKey:\n"
    "    spec_bundle_hash: str\n"
    "    gate_inputs_hash: str\n"
    "    gate_version: str\n"
    "    model_pin: str\n"
    "\n"
    "\n"
    "@dataclasses.dataclass\n"
    "class CachedResult:\n"
    "    gate_type: str\n"
    "    payload: dict\n"
    "    stored_at: str\n"
    "\n"
    "\n"
    "class Miss:\n"
    "    def __eq__(self, other):\n"
    "        return isinstance(other, Miss)\n"
    "\n"
    "    def __hash__(self):\n"
    "        return 0\n"
    "\n"
    "\n"
    "class SchemaValidationError(ValueError):\n"
    "    pass\n"
    "\n"
    "\n"
    "def get(cache_key, *, repo_root=None):\n"
    "    return Miss()\n"
    "\n"
    "\n"
    "def put(cache_key, result, *, repo_root=None):\n"
    "    return None\n"
    "\n"
    "\n"
    "def now_iso():\n"
    "    return time.strftime(" + repr("%Y-%m-%dT%H:%M:%SZ") + ", time.gmtime())\n"
    "\n"
    "\n"
    "def stats(*, repo_root=None):\n"
    "    return " + repr({"entry_count": 0}) + "\n"
)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _no_network(*args, **kwargs):
    raise AssertionError("no webhook call expected in this test")


@pytest.fixture(autouse=True)
def _isolate(monkeypatch):
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    monkeypatch.setattr(urllib.request, "urlopen", _no_network)


def _make_repo(base: Path, name: str) -> Path:
    repo = base / name
    (repo / "gen" / "cache-manager").mkdir(parents=True)
    (repo / "gen" / "cache-manager" / "cache_manager.py").write_text(FAKE_CACHE_MANAGER)
    return repo


def test_full_scan_clean_json_returns_0(tmp_path, monkeypatch, capsys):
    repo = _make_repo(tmp_path, "clean")
    (repo / "gen" / "foo").mkdir(parents=True)
    (repo / "gen" / "foo" / "a.py").write_text("X = 1\n")
    monkeypatch.chdir(tmp_path)

    code = secret_scanner.main(["--repo-root=" + str(repo), "--format=json"])
    out = capsys.readouterr().out

    assert code == 0
    doc = json.loads(out)
    assert field(doc, "flagged") is False


def test_full_scan_flagged_text_space_form_returns_1(tmp_path, monkeypatch, capsys):
    repo = _make_repo(tmp_path, "dirty")
    (repo / "gen" / "foo").mkdir(parents=True)
    (repo / "gen" / "foo" / "c.py").write_text("K = " + repr(AWS_KEY) + "\n")
    monkeypatch.chdir(tmp_path)

    code = secret_scanner.main(["--repo-root", str(repo), "--format", "text"])
    out = capsys.readouterr().out

    assert code == 1
    assert "FLAGGED" in out


def test_precommit_repeatable_files(tmp_path, monkeypatch, capsys):
    repo = tmp_path / "pc"
    repo.mkdir()
    clean = repo / "clean.py"
    clean.write_text("X = 1\n")
    secret = repo / "secret.py"
    secret.write_text("K = " + repr(AWS_KEY) + "\n")
    monkeypatch.chdir(repo)

    first = secret_scanner.main(
        ["precommit", "--files", str(clean), "--files=" + str(secret)]
    )
    capsys.readouterr()
    second = secret_scanner.main(["precommit", "--files=" + str(clean)])
    capsys.readouterr()

    assert first == 1
    assert second == 0


@pytest.mark.skipif(shutil.which("git") is None, reason="git not available")
def test_precommit_defaults_to_git_changed_files(tmp_path, monkeypatch, capsys):
    repo = tmp_path / "gitrepo"
    repo.mkdir()

    def git(*args):
        subprocess.run(
            [
                "git",
                "-c", "user.name=test",
                "-c", "user.email=test@example.invalid",
                "-c", "commit.gpgsign=false",
                *args,
            ],
            cwd=str(repo),
            check=True,
            capture_output=True,
        )

    git("init", "-q")
    (repo / "clean.py").write_text("X = 1\n")
    git("add", "clean.py")
    git("commit", "-q", "-m", "init")
    (repo / "new.py").write_text("K = " + repr(AWS_KEY) + "\n")
    git("add", "new.py")
    monkeypatch.chdir(tmp_path)

    code = secret_scanner.main(["precommit", "--repo-root", str(repo)])
    capsys.readouterr()

    assert code == 1


@pytest.mark.parametrize(
    "argv",
    [
        ["--format=bogus"],
        ["--hotdocs-smoke-unknown"],
        ["bogus-subcommand"],
        ["--repo-root"],
        ["propose", "--format=json"],
    ],
)
def test_usage_errors_return_2(argv, tmp_path, monkeypatch, capsys):
    repo = _make_repo(tmp_path, "usage")
    (repo / "a.py").write_text("X = 1\n")
    monkeypatch.chdir(repo)

    code = secret_scanner.main(argv)
    capsys.readouterr()

    assert code == 2