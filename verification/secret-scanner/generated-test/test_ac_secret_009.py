import json

import secret_scanner


FAKE_CACHE_MANAGER_SRC = r"""
import json
import os


def _env(name):
    return os.environ[name]


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


class Miss:
    pass


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _key_str(cache_key):
    return "|".join([
        str(_get(cache_key, "spec_bundle_hash")),
        str(_get(cache_key, "gate_inputs_hash")),
        str(_get(cache_key, "gate_version")),
        str(_get(cache_key, "model_pin")),
    ])


def _load_store():
    path = _env("FAKE_CACHE_STORE_PATH")
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {}


def _save_store(store):
    path = _env("FAKE_CACHE_STORE_PATH")
    with open(path, "w") as f:
        json.dump(store, f)


def get(cache_key, *, repo_root=None):
    store = _load_store()
    k = _key_str(cache_key)
    if k in store:
        entry = store[k]
        return CachedResult(
            gate_type=entry["gate_type"],
            payload=entry["payload"],
            stored_at=entry["stored_at"],
        )
    return Miss()


def put(cache_key, result, *, repo_root=None):
    store = _load_store()
    k = _key_str(cache_key)
    store[k] = {
        "gate_type": _get(result, "gate_type"),
        "payload": _get(result, "payload"),
        "stored_at": _get(result, "stored_at"),
    }
    _save_store(store)
    log_path = _env("FAKE_CACHE_PUT_LOG_PATH")
    with open(log_path, "a") as f:
        f.write(k + "\n")
"""


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def test_ac_secret_009(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    (repo_root / "specs").mkdir(parents=True)
    (repo_root / "gen").mkdir(parents=True)
    (repo_root / "verification").mkdir(parents=True)

    cache_manager_dir = repo_root / "gen" / "cache-manager"
    cache_manager_dir.mkdir(parents=True)
    (cache_manager_dir / "cache_manager.py").write_text(FAKE_CACHE_MANAGER_SRC)

    patterns_path = tmp_path / "patterns.json"
    patterns_path.write_text(json.dumps({
        "version": "2.0.0",
        "rules": [
            {"rule_id": "aws-access-key-id", "risk_tier": "high", "pattern": "AKIA[0-9A-Z]{16}"},
        ],
    }))

    store_path = tmp_path / "cache_store.json"
    put_log_path = tmp_path / "put_log.txt"

    monkeypatch.setenv("VAR_SECRET_PATTERNS_PATH", str(patterns_path))
    monkeypatch.setenv("FAKE_CACHE_STORE_PATH", str(store_path))
    monkeypatch.setenv("FAKE_CACHE_PUT_LOG_PATH", str(put_log_path))
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)

    secret_file = repo_root / "gen" / "config.py"
    secret_file.write_text('API_KEY = "AKIAABCDEFGHIJKLMNOP"\n')

    result1 = secret_scanner.scan(repo_root)
    assert _get(result1, "flagged") is True

    secret_file.write_text('API_KEY = "REDACTED"\n')

    result2 = secret_scanner.scan(repo_root)
    assert _get(result2, "flagged") is False

    assert put_log_path.exists()
    log_lines = [line for line in put_log_path.read_text().splitlines() if line]
    assert len(log_lines) == 2

    first_key, second_key = log_lines[0], log_lines[1]
    assert first_key != second_key

    store = json.loads(store_path.read_text())
    assert first_key in store
    assert second_key in store

    first_entry_payload = store[first_key]["payload"]
    assert _get(first_entry_payload, "flagged") is True

    second_entry_payload = store[second_key]["payload"]
    assert _get(second_entry_payload, "flagged") is False