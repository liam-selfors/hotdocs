import importlib.metadata
import json
import os
import sys

import secret_scanner


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _expected_gate_version():
    installed = importlib.metadata.version("detect-secrets")
    return "secret_scanner@3.1.0+detect-secrets." + installed


FAKE_CACHE_MANAGER_SOURCE = r"""
import dataclasses
import json
import os


@dataclasses.dataclass
class CacheKey:
    spec_bundle_hash: str
    gate_inputs_hash: str
    gate_version: str
    model_pin: str


@dataclasses.dataclass
class CachedResult:
    gate_type: str
    payload: dict
    stored_at: str


class Miss:
    pass


def _store_path():
    return os.environ["AC_SECRET_006_STORE_PATH"]


def _log_path():
    return os.environ["AC_SECRET_006_LOG_PATH"]


def _load_store():
    path = _store_path()
    if not os.path.exists(path):
        return {}
    with open(path, "r") as fh:
        return json.load(fh)


def _save_store(store):
    with open(_store_path(), "w") as fh:
        json.dump(store, fh)


def _append_log(event):
    with open(_log_path(), "a") as fh:
        fh.write(event + "\n")


def _entry_key(cache_key):
    return cache_key.spec_bundle_hash + "|" + cache_key.gate_inputs_hash


def get(cache_key, *, repo_root=None):
    _append_log("get")
    store = _load_store()
    entry = store.get(_entry_key(cache_key))
    if entry is None:
        return Miss()
    if entry.get("gate_version") != cache_key.gate_version:
        return Miss()
    if entry.get("model_pin") != cache_key.model_pin:
        return Miss()
    return CachedResult(
        gate_type=entry["gate_type"],
        payload=entry["payload"],
        stored_at=entry["stored_at"],
    )


def put(cache_key, cached_result, *, repo_root=None):
    _append_log("put")
    store = _load_store()
    payload = cached_result.payload
    if not isinstance(payload, dict):
        payload = dict(payload)
    store[_entry_key(cache_key)] = {
        "gate_type": cached_result.gate_type,
        "payload": payload,
        "stored_at": cached_result.stored_at,
        "gate_version": cache_key.gate_version,
        "model_pin": cache_key.model_pin,
    }
    _save_store(store)
"""


def test_full_scan_gate_version_matches_installed_detect_secrets_version(tmp_path):
    repo_root = tmp_path / "repo1"
    repo_root.mkdir()

    expected = _expected_gate_version()

    result = secret_scanner.scan(repo_root)
    assert _get(result, "gate_version") == expected
    assert secret_scanner.gate_version(repo_root) == expected


def test_stale_gate_version_cache_entry_is_not_reused(tmp_path):
    repo_root = tmp_path / "repo2"
    cache_manager_dir = repo_root / "gen" / "cache-manager"
    cache_manager_dir.mkdir(parents=True)
    (cache_manager_dir / "cache_manager.py").write_text(FAKE_CACHE_MANAGER_SOURCE)

    store_path = tmp_path / "store.json"
    log_path = tmp_path / "log.txt"
    os.environ["AC_SECRET_006_STORE_PATH"] = str(store_path)
    os.environ["AC_SECRET_006_LOG_PATH"] = str(log_path)

    original_dont_write_bytecode = sys.dont_write_bytecode
    sys.dont_write_bytecode = True

    try:
        result_a = secret_scanner.scan(repo_root)
        assert _get(result_a, "flagged") is False

        log_after_a = log_path.read_text().splitlines()
        assert log_after_a.count("get") == 1
        assert log_after_a.count("put") == 1

        store = json.loads(store_path.read_text())
        assert len(store) == 1
        (entry_key,) = store.keys()
        entry = store[entry_key]
        assert entry["gate_type"] == "secret_scanner"
        assert entry["gate_version"] == _expected_gate_version()

        entry["gate_version"] = "secret_scanner@0.0.1+detect-secrets.0.0.0"
        entry["payload"]["flagged"] = True
        entry["payload"]["matches"] = [
            {
                "rule_id": "stale-cache-marker",
                "risk_tier": "high",
                "file": "nonexistent.txt",
                "line": 1,
            }
        ]
        store[entry_key] = entry
        store_path.write_text(json.dumps(store))

        result_b = secret_scanner.scan(repo_root)

        assert _get(result_b, "cache_hit") is False
        assert _get(result_b, "flagged") is False
        assert _get(result_b, "matches") == []

        log_after_b = log_path.read_text().splitlines()
        assert log_after_b.count("get") == 2
        assert log_after_b.count("put") == 2
    finally:
        sys.dont_write_bytecode = original_dont_write_bytecode
        os.environ.pop("AC_SECRET_006_STORE_PATH", None)
        os.environ.pop("AC_SECRET_006_LOG_PATH", None)