import json
from pathlib import Path

import secret_scanner


_FAKE_CACHE_MANAGER_SOURCE = '''
import json
import os
from dataclasses import dataclass
from typing import Any


@dataclass
class CacheKey:
    spec_bundle_hash: str
    gate_inputs_hash: str
    gate_version: str
    model_pin: str


@dataclass
class CachedResult:
    gate_type: str
    payload: Any
    stored_at: str


class Miss:
    pass


def _log(event):
    path = os.environ.get("FAKE_CACHE_MANAGER_LOG")
    if path:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(event + "\\n")


def _payload():
    raw = os.environ.get("FAKE_CACHE_PAYLOAD_JSON")
    return json.loads(raw) if raw else None


def get(cache_key, *, repo_root=None):
    _log("get")
    return CachedResult(
        gate_type="secret_scanner",
        payload=_payload(),
        stored_at="2026-01-01T00:00:00Z",
    )


def put(cache_key, result, *, repo_root=None):
    _log("put")
    return None
'''


def _field(obj, name):
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


def test_full_scan_cache_hit_returns_cached_matches_and_skips_put(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    specs_file = repo_root / "specs" / "README.md"
    specs_file.parent.mkdir(parents=True, exist_ok=True)
    specs_file.write_text("# nothing secret here\n", encoding="utf-8")

    src_file = repo_root / "src" / "app.py"
    src_file.parent.mkdir(parents=True, exist_ok=True)
    src_file.write_text("print('hello world')\n", encoding="utf-8")

    allowlist_file = repo_root / ".secret-allowlist.json"
    allowlist_file.write_text(
        json.dumps({"version": 1, "entries": []}),
        encoding="utf-8",
    )

    cache_manager_dir = repo_root / "gen" / "cache-manager"
    cache_manager_dir.mkdir(parents=True, exist_ok=True)
    (cache_manager_dir / "cache_manager.py").write_text(
        _FAKE_CACHE_MANAGER_SOURCE, encoding="utf-8"
    )

    log_path = tmp_path / "cache_manager_calls.log"

    cached_matches = [
        {
            "rule_id": "Cached-Only-Rule",
            "risk_tier": "high",
            "file": "nonexistent/cached/path.py",
            "line": 7,
        }
    ]
    cached_payload = {
        "scope": "full",
        "gate_version": "secret_scanner@9.9.9+detect-secrets.1.5.0",
        "flagged": True,
        "matches": cached_matches,
        "allowed": [],
        "unused_allowlist_entries": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }

    monkeypatch.setenv("FAKE_CACHE_MANAGER_LOG", str(log_path))
    monkeypatch.setenv("FAKE_CACHE_PAYLOAD_JSON", json.dumps(cached_payload))

    result = secret_scanner.scan(repo_root)

    assert _field(result, "cache_hit") is True
    assert _field(result, "matches") == cached_matches

    if log_path.exists():
        calls = log_path.read_text(encoding="utf-8").splitlines()
    else:
        calls = []

    assert "get" in calls
    assert "put" not in calls