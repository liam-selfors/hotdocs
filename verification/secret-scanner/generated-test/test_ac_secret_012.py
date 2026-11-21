# hotdocs-criterion: sha256:d43d722dfbeec4a4c3bc846e0a33ecd3d6a45ea9454ad8132501f2078d48af83
import os
import sys
import urllib.request
from pathlib import Path

import pytest

import secret_scanner


LOG_ENV = "SECRET_SCANNER_AC012_CACHE_LOG"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _fake_cache_manager_source():
    lines = [
        "import dataclasses",
        "import os",
        "import time",
        "",
        "LOG_ENV = " + repr(LOG_ENV),
        "",
        "",
        "def _log(name):",
        "    p = os.environ.get(LOG_ENV)",
        "    if p:",
        "        with open(p, 'a') as fh:",
        "            fh.write(name + chr(10))",
        "",
        "",
        "class SchemaValidationError(ValueError):",
        "    pass",
        "",
        "",
        "class Miss:",
        "    def __eq__(self, other):",
        "        return isinstance(other, Miss)",
        "",
        "    def __hash__(self):",
        "        return 0",
        "",
        "",
        "@dataclasses.dataclass",
        "class CacheKey:",
        "    spec_bundle_hash: str",
        "    gate_inputs_hash: str",
        "    gate_version: str",
        "    model_pin: str",
        "",
        "    def __post_init__(self):",
        "        _log('CacheKey')",
        "",
        "",
        "@dataclasses.dataclass",
        "class CachedResult:",
        "    gate_type: str",
        "    payload: dict",
        "    stored_at: str",
        "",
        "    def __post_init__(self):",
        "        _log('CachedResult')",
        "",
        "",
        "def get(cache_key, *, repo_root=None):",
        "    _log('get')",
        "    return Miss()",
        "",
        "",
        "def put(cache_key, result, *, repo_root=None):",
        "    _log('put')",
        "    return None",
        "",
        "",
        "def now_iso():",
        "    _log('now_iso')",
        "    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())",
        "",
        "",
        "def stats(*, repo_root=None):",
        "    _log('stats')",
        "    return dict(entry_count=0)",
        "",
    ]
    return "\n".join(lines)


def _write_fake_cache_manager(repo_root):
    d = repo_root / "gen" / "cache-manager"
    d.mkdir(parents=True, exist_ok=True)
    (d / "cache_manager.py").write_text(_fake_cache_manager_source())


def _write_secret_file(repo_root):
    # Built at runtime so this test file holds no detectable literal.
    key = "AKIA" + "IOSFODNN7" + "EXAMPLE"
    src = "AWS_ACCESS_KEY_ID = " + repr(key) + "\n"
    target = repo_root / "src" / "config.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(src)


def _snapshot(root):
    snap = {}
    st = root.stat()
    snap["."] = ("dir", None, st.st_mtime_ns)
    for p in sorted(root.rglob("*")):
        rel = p.relative_to(root).as_posix()
        st = p.stat()
        if p.is_dir():
            snap[rel] = ("dir", None, st.st_mtime_ns)
        else:
            snap[rel] = ("file", p.read_bytes(), st.st_mtime_ns)
    return snap


@pytest.fixture
def env(tmp_path, monkeypatch):
    log_dir = tmp_path / "log"
    log_dir.mkdir()
    log_path = log_dir / "calls.log"
    monkeypatch.setenv(LOG_ENV, str(log_path))
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)

    def _no_network(*args, **kwargs):
        raise OSError("network disabled in test")

    monkeypatch.setattr(urllib.request, "urlopen", _no_network)
    monkeypatch.setattr(sys, "dont_write_bytecode", True)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    return repo_root, log_path


@pytest.mark.parametrize("with_secret", [False, True])
def test_gate_version_matches_scan_result(env, with_secret):
    repo_root, _log_path = env
    _write_fake_cache_manager(repo_root)
    if with_secret:
        _write_secret_file(repo_root)

    version = secret_scanner.gate_version(repo_root)
    result = secret_scanner.scan(repo_root)

    assert isinstance(version, str)
    assert version == field(result, "gate_version")


def test_gate_version_does_not_scan_call_cache_or_write(env):
    repo_root, log_path = env
    _write_fake_cache_manager(repo_root)
    _write_secret_file(repo_root)

    before = _snapshot(repo_root)

    version = secret_scanner.gate_version(repo_root)

    after = _snapshot(repo_root)

    assert isinstance(version, str)
    calls = log_path.read_text().splitlines() if log_path.exists() else []
    assert calls == [], "cache-manager stand-in was called: " + repr(calls)
    assert sorted(after.keys()) == sorted(before.keys()), (
        "files created or removed under repo_root: "
        + repr(sorted(set(after) ^ set(before)))
    )
    for rel, entry in before.items():
        assert after[rel] == entry, "changed under repo_root: " + repr(rel)