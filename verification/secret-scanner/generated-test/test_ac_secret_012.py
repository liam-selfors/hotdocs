import hashlib
import os
import tempfile
from pathlib import Path

import secret_scanner


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _snapshot(root):
    snap = {}
    for dirpath, _dirnames, filenames in os.walk(root):
        for fn in filenames:
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, root)
            with open(full, "rb") as f:
                content_hash = hashlib.sha256(f.read()).hexdigest()
            st = os.stat(full)
            snap[rel] = (content_hash, st.st_mtime_ns)
    return snap


_CACHE_MANAGER_SOURCE = '''
import os


class CacheKey:
    def __init__(self, spec_bundle_hash=None, gate_inputs_hash=None,
                 gate_version=None, model_pin=None):
        self.spec_bundle_hash = spec_bundle_hash
        self.gate_inputs_hash = gate_inputs_hash
        self.gate_version = gate_version
        self.model_pin = model_pin


class CachedResult:
    def __init__(self, gate_type=None, payload=None, stored_at=None):
        self.gate_type = gate_type
        self.payload = payload
        self.stored_at = stored_at


class Miss:
    pass


def _record(call_name):
    log_path = os.environ.get("AC_SECRET_012_CACHE_LOG")
    if log_path:
        with open(log_path, "a") as f:
            f.write(call_name + "\\n")


def get(cache_key, repo_root=None):
    _record("get")
    return Miss()


def put(cache_key, result, repo_root=None):
    _record("put")
    return None
'''


def test_gate_version_matches_scan_gate_version():
    with tempfile.TemporaryDirectory() as repo_root_str:
        repo_root = Path(repo_root_str)
        (repo_root / "readme.txt").write_text("nothing interesting here\n")

        scan_result = secret_scanner.scan(repo_root)
        reported = secret_scanner.gate_version(repo_root)

        assert isinstance(reported, str)
        assert reported == _get(scan_result, "gate_version")


def test_gate_version_never_calls_cache_manager_or_touches_files():
    with tempfile.TemporaryDirectory() as repo_root_str, \
            tempfile.TemporaryDirectory() as log_dir_str:
        repo_root = Path(repo_root_str)
        log_path = os.path.join(log_dir_str, "cache_calls.log")

        secret_file = repo_root / "app_config.py"
        secret_file.write_text(
            'AWS_ACCESS_KEY = "AKIAIOSFODNN7EXAMPLE"\n'
        )

        cache_manager_dir = repo_root / "gen" / "cache-manager"
        cache_manager_dir.mkdir(parents=True)
        (cache_manager_dir / "cache_manager.py").write_text(_CACHE_MANAGER_SOURCE)

        old_env = os.environ.get("AC_SECRET_012_CACHE_LOG")
        os.environ["AC_SECRET_012_CACHE_LOG"] = log_path
        try:
            before = _snapshot(repo_root)

            result = secret_scanner.gate_version(repo_root)

            after = _snapshot(repo_root)
        finally:
            if old_env is None:
                os.environ.pop("AC_SECRET_012_CACHE_LOG", None)
            else:
                os.environ["AC_SECRET_012_CACHE_LOG"] = old_env

        assert isinstance(result, str)
        assert not os.path.exists(log_path) or os.path.getsize(log_path) == 0
        assert before == after