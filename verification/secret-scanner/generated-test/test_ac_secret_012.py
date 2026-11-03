import hashlib
import os
import tempfile
from pathlib import Path

import pytest

pytest.importorskip("detect_secrets")

import secret_scanner


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _snapshot(root):
    snap = {}
    for p in sorted(root.rglob("*")):
        if p.is_file():
            rel = p.relative_to(root).as_posix()
            snap[rel] = hashlib.sha256(p.read_bytes()).hexdigest()
    return snap


FAKE_CACHE_MANAGER_SOURCE = '''
import os


class CacheKey:
    def __init__(self, spec_bundle_hash=None, gate_inputs_hash=None,
                 gate_version=None, model_pin=None):
        self.spec_bundle_hash = spec_bundle_hash
        self.gate_inputs_hash = gate_inputs_hash
        self.gate_version = gate_version
        self.model_pin = model_pin
        _log("CacheKey")


class CachedResult:
    def __init__(self, gate_type=None, payload=None, stored_at=None):
        self.gate_type = gate_type
        self.payload = payload
        self.stored_at = stored_at
        _log("CachedResult")


def _log(call):
    log_path = os.environ.get("FAKE_CACHE_MANAGER_LOG")
    if log_path:
        with open(log_path, "a") as f:
            f.write(call + "\\n")


def get(cache_key, repo_root=None):
    _log("get")
    return None


def put(cache_key, cached_result, repo_root=None):
    _log("put")
    return None
'''


def test_gate_version_matches_scan_result(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / "README.md").write_text("hello world\n")

    scan_result = secret_scanner.scan(repo_root)
    version = secret_scanner.gate_version(repo_root)

    assert isinstance(version, str)
    assert version == _get(scan_result, "gate_version")


def test_gate_version_does_not_scan_or_touch_cache_or_files(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    secret_file = repo_root / "config.py"
    secret_file.write_text(
        'AWS_SECRET_ACCESS_KEY = "AKIAIOSFODNN7EXAMPLE"\n'
    )

    cache_manager_dir = repo_root / "gen" / "cache-manager"
    cache_manager_dir.mkdir(parents=True)
    (cache_manager_dir / "cache_manager.py").write_text(FAKE_CACHE_MANAGER_SOURCE)

    log_dir = tempfile.mkdtemp()
    log_path = os.path.join(log_dir, "calls.log")
    monkeypatch.setenv("FAKE_CACHE_MANAGER_LOG", log_path)

    before = _snapshot(repo_root)

    version = secret_scanner.gate_version(repo_root)

    after = _snapshot(repo_root)

    assert isinstance(version, str)
    assert before == after
    assert not os.path.exists(log_path)