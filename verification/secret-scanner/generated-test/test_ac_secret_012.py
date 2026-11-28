# hotdocs-criterion: sha256:44b85fde140a55ff77cfdd7f62abe5b82b3d8267155075a06392cf5d6c109847
import os
import sys
import urllib.request
from pathlib import Path

import pytest

import secret_scanner


LOG_ENV = "SECRET_SCANNER_TEST_CM_LOG"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _fake_cache_manager_source():
    return (
        "import os\n"
        "from dataclasses import dataclass\n"
        "from pathlib import Path\n"
        "\n"
        "_LOG_ENV = " + repr(LOG_ENV) + "\n"
        "\n"
        "\n"
        "def _log(name):\n"
        "    path = os.environ.get(_LOG_ENV)\n"
        "    if path:\n"
        "        with open(path, 'a', encoding='utf-8') as fh:\n"
        "            fh.write(name + '\\n')\n"
        "\n"
        "\n"
        "class SchemaValidationError(ValueError):\n"
        "    pass\n"
        "\n"
        "\n"
        "class Miss:\n"
        "    def __eq__(self, other):\n"
        "        return isinstance(other, Miss)\n"
        "\n"
        "    def __hash__(self):\n"
        "        return hash('Miss')\n"
        "\n"
        "\n"
        "@dataclass\n"
        "class CacheKey:\n"
        "    spec_bundle_hash: str\n"
        "    gate_inputs_hash: str\n"
        "    gate_version: str\n"
        "    model_pin: str\n"
        "\n"
        "    def __post_init__(self):\n"
        "        _log('CacheKey')\n"
        "\n"
        "\n"
        "@dataclass\n"
        "class CachedResult:\n"
        "    gate_type: str\n"
        "    payload: dict\n"
        "    stored_at: str\n"
        "\n"
        "    def __post_init__(self):\n"
        "        _log('CachedResult')\n"
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
        "    _log('now_iso')\n"
        "    return '2026-01-01T00:00:00Z'\n"
        "\n"
        "\n"
        "def stats(*, repo_root=None):\n"
        "    _log('stats')\n"
        "    return {'entry_count': 0}\n"
    )


def _write_fake_cache_manager(repo_root):
    target = repo_root / "gen" / "cache-manager" / "cache_manager.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(_fake_cache_manager_source(), encoding="utf-8")
    return target


def _snapshot(root):
    snap = {}
    for dirpath, dirnames, filenames in os.walk(root):
        d = Path(dirpath)
        snap[("dir", str(d.relative_to(root)))] = None
        for name in filenames:
            p = d / name
            st = p.stat()
            snap[("file", str(p.relative_to(root)))] = (
                p.read_bytes(),
                st.st_mtime_ns,
                st.st_size,
            )
    return snap


@pytest.fixture
def isolated_env(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    monkeypatch.setattr(sys, "dont_write_bytecode", True)

    webhook_calls = []

    def fake_urlopen(*args, **kwargs):
        webhook_calls.append((args, kwargs))
        raise OSError("network disabled in test")

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    log_file = log_dir / "cache_manager_calls.log"
    monkeypatch.setenv(LOG_ENV, str(log_file))

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    return repo_root, log_file, webhook_calls


def _read_log(log_file):
    if not log_file.exists():
        return []
    return [line for line in log_file.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_gate_version_matches_scan_result(isolated_env):
    repo_root, log_file, _ = isolated_env
    _write_fake_cache_manager(repo_root)
    (repo_root / "README.md").write_text("hello world\n", encoding="utf-8")

    version = secret_scanner.gate_version(repo_root)
    result = secret_scanner.scan(repo_root)

    assert isinstance(version, str)
    assert version
    assert version == field(result, "gate_version")


def test_gate_version_does_not_call_cache_manager_or_write(isolated_env):
    repo_root, log_file, webhook_calls = isolated_env
    _write_fake_cache_manager(repo_root)

    secret_dir = repo_root / "gen" / "foo"
    secret_dir.mkdir(parents=True, exist_ok=True)
    aws_key = "AKIA" + "IOSFODNN7" + "EXAMPLE"
    (secret_dir / "config.py").write_text(
        "AWS_ACCESS_KEY_ID = " + repr(aws_key) + "\n", encoding="utf-8"
    )

    before = _snapshot(repo_root)

    version = secret_scanner.gate_version(repo_root)

    after = _snapshot(repo_root)

    assert isinstance(version, str)
    assert version
    assert _read_log(log_file) == [], "cache-manager stand-in was called"
    assert after == before, "gate_version created or changed files under repo_root"
    assert webhook_calls == []