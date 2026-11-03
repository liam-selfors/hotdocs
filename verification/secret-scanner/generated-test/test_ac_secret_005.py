import json
import os
import tempfile
from pathlib import Path

import secret_scanner


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


_FAKE_CACHE_MANAGER_SOURCE = r'''
import json
import os


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


CALL_LOG = os.environ["AC_SECRET_005_CALL_LOG"]
_CACHED_PAYLOAD = json.loads(os.environ["AC_SECRET_005_CACHED_PAYLOAD"])


class CacheKey:
    def __init__(self, spec_bundle_hash, gate_inputs_hash, gate_version, model_pin):
        self.spec_bundle_hash = spec_bundle_hash
        self.gate_inputs_hash = gate_inputs_hash
        self.gate_version = gate_version
        self.model_pin = model_pin


class CachedResult:
    def __init__(self, gate_type, payload, stored_at):
        self.gate_type = gate_type
        self.payload = payload
        self.stored_at = stored_at


def get(cache_key, *, repo_root=None):
    record = {
        "op": "get",
        "spec_bundle_hash": _get(cache_key, "spec_bundle_hash"),
        "gate_inputs_hash": _get(cache_key, "gate_inputs_hash"),
        "gate_version": _get(cache_key, "gate_version"),
        "model_pin": _get(cache_key, "model_pin"),
    }
    with open(CALL_LOG, "a") as f:
        f.write(json.dumps(record) + "\n")
    return CachedResult(
        gate_type="secret_scanner",
        payload=_CACHED_PAYLOAD,
        stored_at="2026-01-01T00:00:00Z",
    )


def put(cache_key, cached_result, *, repo_root=None):
    with open(CALL_LOG, "a") as f:
        f.write(json.dumps({"op": "put"}) + "\n")
'''


def test_full_scan_cache_hit_returns_cached_matches_and_skips_put():
    with tempfile.TemporaryDirectory() as repo_root_str, tempfile.TemporaryDirectory() as side_dir:
        repo_root = Path(repo_root_str)

        specs_dir = repo_root / "specs"
        specs_dir.mkdir(parents=True)
        (specs_dir / "readme.md").write_text("hello world\n")

        app_dir = repo_root / "app"
        app_dir.mkdir(parents=True)
        (app_dir / "config.py").write_text('AWS_KEY = "AKIAABCDEFGHIJKLMNOP"\n')

        cache_manager_dir = repo_root / "gen" / "cache-manager"
        cache_manager_dir.mkdir(parents=True)
        (cache_manager_dir / "cache_manager.py").write_text(_FAKE_CACHE_MANAGER_SOURCE)

        call_log_path = Path(side_dir) / "cache_calls.jsonl"

        cached_matches = [
            {
                "rule_id": "Historical Secret",
                "risk_tier": "high",
                "file": "old/vanished.py",
                "line": 7,
            }
        ]
        cached_payload = {
            "scope": "full",
            "gate_version": "secret_scanner@3.0.0+detect-secrets.1.5.0",
            "flagged": True,
            "matches": cached_matches,
            "allowed": [],
            "unused_allowlist_entries": [],
            "notified": False,
            "notification_delivery_error": None,
            "cache_hit": False,
        }

        old_call_log = os.environ.get("AC_SECRET_005_CALL_LOG")
        old_payload = os.environ.get("AC_SECRET_005_CACHED_PAYLOAD")
        os.environ["AC_SECRET_005_CALL_LOG"] = str(call_log_path)
        os.environ["AC_SECRET_005_CACHED_PAYLOAD"] = json.dumps(cached_payload)
        try:
            result = secret_scanner.scan(repo_root)
        finally:
            if old_call_log is None:
                os.environ.pop("AC_SECRET_005_CALL_LOG", None)
            else:
                os.environ["AC_SECRET_005_CALL_LOG"] = old_call_log
            if old_payload is None:
                os.environ.pop("AC_SECRET_005_CACHED_PAYLOAD", None)
            else:
                os.environ["AC_SECRET_005_CACHED_PAYLOAD"] = old_payload

        assert _get(result, "cache_hit") is True
        assert _get(result, "matches") == cached_matches

        assert call_log_path.exists(), "cache-manager was never consulted"
        ops = []
        with open(call_log_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                ops.append(json.loads(line))

        assert any(entry["op"] == "get" for entry in ops), "get() was never called"
        assert all(entry["op"] != "put" for entry in ops), "put() must not be called on a cache hit"

        get_entries = [entry for entry in ops if entry["op"] == "get"]
        last_get = get_entries[-1]
        assert last_get["spec_bundle_hash"].startswith("sha256:")
        assert last_get["gate_inputs_hash"].startswith("sha256:")
        assert last_get["model_pin"] == "none"