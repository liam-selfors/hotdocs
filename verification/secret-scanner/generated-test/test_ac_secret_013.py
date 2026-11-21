# hotdocs-criterion: sha256:54609f143f35ca56eccb04ea64830f4c442b71172c0abcc36d316643daf0e6bc
import json
import os
import shutil
import subprocess
import urllib.request
from pathlib import Path

import pytest

import secret_scanner


# Built by concatenation so this test file itself holds no detectable key.
AWS_KEY = "AKIA" + "ABCDEFGHIJKLMNOP"

CACHE_LOG_ENV = "SECRET_SCAN_TEST_CACHE_LOG"

FAKE_CACHE_MANAGER_SOURCE = (
    "import datetime\n"
    "import os\n"
    "from dataclasses import dataclass\n"
    "\n"
    "\n"
    "def _log(line):\n"
    "    p = os.environ.get(" + repr(CACHE_LOG_ENV) + ")\n"
    "    if p:\n"
    "        with open(p, 'a') as f:\n"
    "            f.write(line + '\\n')\n"
    "\n"
    "\n"
    "@dataclass\n"
    "class CacheKey:\n"
    "    spec_bundle_hash: str\n"
    "    gate_inputs_hash: str\n"
    "    gate_version: str\n"
    "    model_pin: str\n"
    "\n"
    "\n"
    "@dataclass\n"
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
    "    _log('get')\n"
    "    return Miss()\n"
    "\n"
    "\n"
    "def put(cache_key, result, *, repo_root=None):\n"
    "    _log('put')\n"
    "    return None\n"
    "\n"
    "\n"
    "def now_iso():\n"
    "    return datetime.datetime.now(datetime.timezone.utc).strftime("
    + repr("%Y-%m-%dT%H:%M:%SZ")
    + ")\n"
    "\n"
    "\n"
    "def stats(*, repo_root=None):\n"
    "    return {'entry_count': 0}\n"
    "\n"
    "\n"
    "def main(argv=None):\n"
    "    return 0\n"
)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


@pytest.fixture
def env(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    logs = tmp_path / "logs"
    logs.mkdir()
    cm_dir = repo_root / "gen" / "cache-manager"
    cm_dir.mkdir(parents=True)
    (cm_dir / "cache_manager.py").write_text(FAKE_CACHE_MANAGER_SOURCE)
    monkeypatch.setenv(CACHE_LOG_ENV, str(logs / "cache.log"))
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)

    def fake_urlopen(*args, **kwargs):
        raise AssertionError("urlopen must not be called without a webhook URL")

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    monkeypatch.chdir(repo_root)
    return repo_root


def write_clean(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("def add(a, b):\n    return a + b\n")


def write_secret(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("K = " + repr(AWS_KEY).replace("'", '"') + "\n")


def test_full_scan_clean_json_returns_0(env, capsys):
    repo_root = env
    write_clean(repo_root / "gen" / "foo" / "a.py")
    capsys.readouterr()
    rc = secret_scanner.main(["--repo-root=" + str(repo_root), "--format=json"])
    out = capsys.readouterr().out
    assert rc == 0
    doc = json.loads(out)
    assert field(doc, "flagged") is False


def test_full_scan_secret_text_returns_1(env, capsys):
    repo_root = env
    write_secret(repo_root / "gen" / "foo" / "c.py")
    capsys.readouterr()
    rc = secret_scanner.main(["--repo-root", str(repo_root), "--format", "text"])
    out = capsys.readouterr().out
    assert rc == 1
    assert "FLAGGED" in out


def test_precommit_files_repeatable(env, capsys):
    repo_root = env
    clean = repo_root / "clean.py"
    secret = repo_root / "secret.py"
    write_clean(clean)
    write_secret(secret)
    rc1 = secret_scanner.main(
        ["precommit", "--files", str(clean), "--files=" + str(secret)]
    )
    rc2 = secret_scanner.main(["precommit", "--files=" + str(clean)])
    assert rc1 == 1
    assert rc2 == 0


@pytest.mark.skipif(shutil.which("git") is None, reason="git not available")
def test_precommit_default_files_from_git(env, monkeypatch):
    repo_root = env
    for name in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"):
        monkeypatch.delenv(name, raising=False)

    def git(*args):
        subprocess.run(
            [
                "git",
                "-c", "user.email=test@example.com",
                "-c", "user.name=Test",
                "-c", "commit.gpgsign=false",
            ]
            + list(args),
            cwd=str(repo_root),
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    git("init", "-q")
    write_clean(repo_root / "a.py")
    git("add", "a.py")
    git("commit", "-q", "-m", "init")
    write_secret(repo_root / "b.py")
    git("add", "b.py")

    rc = secret_scanner.main(["precommit", "--repo-root", str(repo_root)])
    assert rc == 1


@pytest.mark.parametrize(
    "argv_builder",
    [
        lambda root: ["--repo-root", root, "--format=bogus"],
        lambda root: ["--repo-root", root, "--hotdocs-smoke-unknown"],
        lambda root: ["frobnicate-subcommand", "--repo-root", root],
        lambda root: ["--repo-root"],
        lambda root: ["propose", "--format=json"],
    ],
    ids=["bogus-format", "unknown-arg", "unknown-subcommand", "dangling-flag", "propose-format"],
)
def test_usage_errors_return_2(env, capsys, argv_builder):
    repo_root = env
    write_clean(repo_root / "gen" / "foo" / "a.py")
    rc = secret_scanner.main(argv_builder(str(repo_root)))
    assert rc == 2
    err = capsys.readouterr().err
    assert "Traceback" not in err