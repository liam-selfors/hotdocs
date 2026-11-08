import importlib.metadata
import json

import secret_scanner


def _field(obj, name, default=None):
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


FAKE_CACHE_MANAGER_SOURCE = '''
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


def _store_path():
    return os.environ["FAKE_CACHE_STORE_FILE"]


def _log_path():
    return os.environ["FAKE_CACHE_LOG_FILE"]


def _load_store():
    path = _store_path()
    if not os.path.exists(path):
        return []
    with open(path) as f:
        content = f.read()
    if not content:
        return []
    return json.loads(content)


def _save_store(entries):
    with open(_store_path(), "w") as f:
        json.dump(entries, f)


def _log(event, cache_key):
    with open(_log_path(), "a") as f:
        f.write(json.dumps({
            "event": event,
            "spec_bundle_hash": cache_key.spec_bundle_hash,
            "gate_inputs_hash": cache_key.gate_inputs_hash,
            "gate_version": cache_key.gate_version,
            "model_pin": cache_key.model_pin,
        }) + "\\n")


def get(cache_key, repo_root=None):
    for entry in _load_store():
        if (entry["spec_bundle_hash"] == cache_key.spec_bundle_hash and
                entry["gate_inputs_hash"] == cache_key.gate_inputs_hash and
                entry["gate_version"] == cache_key.gate_version and
                entry["model_pin"] == cache_key.model_pin):
            _log("hit", cache_key)
            return CachedResult(
                gate_type=entry["gate_type"],
                payload=entry["payload"],
                stored_at=entry["stored_at"],
            )
    _log("miss", cache_key)
    return Miss()


def put(cache_key, cached_result, repo_root=None):
    payload = cached_result.get("payload") if isinstance(cached_result, dict) else getattr(cached_result, "payload", None)
    gate_type = cached_result.get("gate_type") if isinstance(cached_result, dict) else getattr(cached_result, "gate_type", None)
    stored_at = cached_result.get("stored_at") if isinstance(cached_result, dict) else getattr(cached_result, "stored_at", None)
    entries = [
        e for e in _load_store()
        if not (e["spec_bundle_hash"] == cache_key.spec_bundle_hash and
                e["gate_inputs_hash"] == cache_key.gate_inputs_hash and
                e["gate_version"] == cache_key.gate_version and
                e["model_pin"] == cache_key.model_pin)
    ]
    entries.append({
        "spec_bundle_hash": cache_key.spec_bundle_hash,
        "gate_inputs_hash": cache_key.gate_inputs_hash,
        "gate_version": cache_key.gate_version,
        "model_pin": cache_key.model_pin,
        "gate_type": gate_type,
        "payload": payload,
        "stored_at": stored_at,
    })
    _save_store(entries)
    _log("put", cache_key)
'''


def _install_fake_cache_manager(repo_root):
    cache_manager_dir = repo_root / "gen" / "cache-manager"
    cache_manager_dir.mkdir(parents=True, exist_ok=True)
    (cache_manager_dir / "cache_manager.py").write_text(FAKE_CACHE_MANAGER_SOURCE)


def _write_clean_repo_contents(repo_root):
    src_dir = repo_root / "src"
    src_dir.mkdir(parents=True, exist_ok=True)
    (src_dir / "app.py").write_text("def greet():\n    return 'hello world'\n")


def test_gate_version_matches_installed_detect_secrets_version(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write_clean_repo_contents(repo_root)
    _install_fake_cache_manager(repo_root)

    support_dir = tmp_path / "support"
    support_dir.mkdir()
    monkeypatch.setenv("FAKE_CACHE_STORE_FILE", str(support_dir / "store.json"))
    monkeypatch.setenv("FAKE_CACHE_LOG_FILE", str(support_dir / "log.jsonl"))

    result = secret_scanner.scan(repo_root)

    installed_version = importlib.metadata.version("detect-secrets")
    expected_gate_version = "secret_scanner@3.1.0+detect-secrets." + installed_version

    actual_gate_version = _field(result, "gate_version")
    assert actual_gate_version == expected_gate_version


def test_stale_gate_version_cache_entry_is_not_reused(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write_clean_repo_contents(repo_root)
    _install_fake_cache_manager(repo_root)

    support_dir = tmp_path / "support"
    support_dir.mkdir()
    store_file = support_dir / "store.json"
    log_file = support_dir / "log.jsonl"
    monkeypatch.setenv("FAKE_CACHE_STORE_FILE", str(store_file))
    monkeypatch.setenv("FAKE_CACHE_LOG_FILE", str(log_file))

    first_result = secret_scanner.scan(repo_root)
    assert _field(first_result, "cache_hit") is False

    log_lines = [json.loads(line) for line in log_file.read_text().splitlines() if line]
    put_entries = [entry for entry in log_lines if entry["event"] == "put"]
    assert len(put_entries) == 1
    real_key = put_entries[0]

    stale_gate_version = real_key["gate_version"] + ".stale-test-marker"
    assert stale_gate_version != real_key["gate_version"]

    stale_store_contents = [{
        "spec_bundle_hash": real_key["spec_bundle_hash"],
        "gate_inputs_hash": real_key["gate_inputs_hash"],
        "gate_version": stale_gate_version,
        "model_pin": real_key["model_pin"],
        "gate_type": "secret_scanner",
        "payload": {
            "scope": "full",
            "gate_version": stale_gate_version,
            "flagged": True,
            "matches": [
                {"rule_id": "stale-cached-sentinel", "risk_tier": "high", "file": "stale.txt", "line": 1}
            ],
            "allowed": [],
            "unused_allowlist_entries": [],
            "notified": False,
            "notification_delivery_error": None,
            "cache_hit": True,
        },
        "stored_at": "2020-01-01T00:00:00Z",
    }]
    store_file.write_text(json.dumps(stale_store_contents))

    log_file.write_text("")

    second_result = secret_scanner.scan(repo_root)

    second_log_lines = [json.loads(line) for line in log_file.read_text().splitlines() if line]
    get_events = [entry["event"] for entry in second_log_lines if entry["gate_version"] != stale_gate_version or entry["event"] == "miss"]
    assert "miss" in [entry["event"] for entry in second_log_lines]
    assert "hit" not in [entry["event"] for entry in second_log_lines]

    assert _field(second_result, "cache_hit") is False

    second_matches = _field(second_result, "matches", [])
    rule_ids = [_field(m, "rule_id") for m in second_matches]
    assert "stale-cached-sentinel" not in rule_ids