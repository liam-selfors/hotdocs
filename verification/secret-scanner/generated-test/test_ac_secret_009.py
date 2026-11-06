import json
import os
import urllib.request

import secret_scanner


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


FAKE_CACHE_MANAGER_SOURCE = '''
import json
import os
from dataclasses import dataclass
from typing import Any

_STORE_PATH = os.environ["AC_SECRET_009_STORE_PATH"]
_LOG_PATH = os.environ["AC_SECRET_009_LOG_PATH"]


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


def _key_str(cache_key):
    return "|".join([
        cache_key.spec_bundle_hash,
        cache_key.gate_inputs_hash,
        cache_key.gate_version,
        cache_key.model_pin,
    ])


def _load_store():
    if os.path.exists(_STORE_PATH):
        with open(_STORE_PATH) as f:
            return json.load(f)
    return {}


def _save_store(store):
    with open(_STORE_PATH, "w") as f:
        json.dump(store, f)


def get(cache_key, repo_root=None):
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


def put(cache_key, cached_result, repo_root=None):
    store = _load_store()
    k = _key_str(cache_key)
    store[k] = {
        "gate_type": cached_result.gate_type,
        "payload": cached_result.payload,
        "stored_at": cached_result.stored_at,
    }
    _save_store(store)
    with open(_LOG_PATH, "a") as f:
        f.write(k + "\\n")
'''


AWS_KEY_LINE = 'K = "AKIAABCDEFGHIJKLMNOP"\n'
CLEAN_LINE = 'K = "removed"\n'


def test_flagged_result_survives_cleanup_under_own_cache_key(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    gen_foo = repo_root / "gen" / "foo"
    gen_foo.mkdir(parents=True)
    target_file = gen_foo / "c.py"
    target_file.write_text(AWS_KEY_LINE)

    cache_manager_dir = repo_root / "gen" / "cache-manager"
    cache_manager_dir.mkdir(parents=True)
    (cache_manager_dir / "cache_manager.py").write_text(FAKE_CACHE_MANAGER_SOURCE)

    store_dir = tmp_path / "store"
    store_dir.mkdir()
    store_path = store_dir / "store.json"
    log_path = store_dir / "put.log"

    monkeypatch.setenv("AC_SECRET_009_STORE_PATH", str(store_path))
    monkeypatch.setenv("AC_SECRET_009_LOG_PATH", str(log_path))
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)

    def _no_network(*args, **kwargs):
        raise AssertionError("urlopen must not be called in this test")

    monkeypatch.setattr(urllib.request, "urlopen", _no_network)

    result1 = secret_scanner.scan(repo_root)
    assert _get(result1, "flagged") is True
    assert _get(result1, "matches")

    assert log_path.exists()
    log_lines_after_first = log_path.read_text().splitlines()
    assert len(log_lines_after_first) == 1
    key1 = log_lines_after_first[0]

    store_after_first = json.loads(store_path.read_text())
    assert key1 in store_after_first
    assert store_after_first[key1]["payload"]["flagged"] is True

    target_file.write_text(CLEAN_LINE)

    result2 = secret_scanner.scan(repo_root)
    assert _get(result2, "flagged") is False

    log_lines_after_second = log_path.read_text().splitlines()
    assert len(log_lines_after_second) == 2
    key2 = log_lines_after_second[1]

    assert key1 != key2

    store_after_second = json.loads(store_path.read_text())
    assert key1 in store_after_second
    assert store_after_second[key1]["payload"]["flagged"] is True
    assert store_after_second[key1]["payload"] == store_after_first[key1]["payload"]

    assert key2 in store_after_second
    assert store_after_second[key2]["payload"]["flagged"] is False