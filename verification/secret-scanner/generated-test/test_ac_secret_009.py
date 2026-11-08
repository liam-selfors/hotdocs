import json
import os
import shutil
import tempfile
from pathlib import Path

import secret_scanner


FAKE_CACHE_MANAGER_SOURCE = '''
import os
import json


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


def _field(obj, name):
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


def _key_tuple(cache_key):
    return (
        _field(cache_key, "spec_bundle_hash"),
        _field(cache_key, "gate_inputs_hash"),
        _field(cache_key, "gate_version"),
        _field(cache_key, "model_pin"),
    )


def _key_str(cache_key):
    return "|".join(str(part) for part in _key_tuple(cache_key))


def _store_path():
    return os.environ["FAKE_CACHE_STORE_PATH"]


def _log_path():
    return os.environ["FAKE_CACHE_LOG_PATH"]


def _load_store():
    path = _store_path()
    if os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f)
    return {}


def _save_store(store):
    with open(_store_path(), "w") as f:
        json.dump(store, f)


def get(cache_key, *, repo_root=None):
    store = _load_store()
    entry = store.get(_key_str(cache_key))
    if entry is None:
        return Miss()
    return CachedResult(
        gate_type=entry["gate_type"],
        payload=entry["payload"],
        stored_at=entry["stored_at"],
    )


def put(cache_key, result, *, repo_root=None):
    store = _load_store()
    key_str = _key_str(cache_key)
    store[key_str] = {
        "gate_type": _field(result, "gate_type"),
        "payload": _field(result, "payload"),
        "stored_at": _field(result, "stored_at"),
    }
    _save_store(store)
    payload = _field(result, "payload")
    flagged = _field(payload, "flagged")
    with open(_log_path(), "a") as f:
        f.write(json.dumps({"key": key_str, "flagged": flagged}) + "\\n")
'''


def _field(obj, name):
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


def test_flagged_result_survives_cache_write_after_clean_rescan():
    repo_root = Path(tempfile.mkdtemp(prefix="hotdocs_secret_scan_repo_"))
    store_dir = Path(tempfile.mkdtemp(prefix="hotdocs_fake_cache_store_"))
    old_environ = dict(os.environ)
    try:
        foo_dir = repo_root / "gen" / "foo"
        foo_dir.mkdir(parents=True)
        c_py = foo_dir / "c.py"
        c_py.write_text('K = "AKIAABCDEFGHIJKLMNOP"\n')

        cache_manager_dir = repo_root / "gen" / "cache-manager"
        cache_manager_dir.mkdir(parents=True)
        cache_manager_file = cache_manager_dir / "cache_manager.py"
        cache_manager_file.write_text(FAKE_CACHE_MANAGER_SOURCE)

        store_path = store_dir / "store.json"
        log_path = store_dir / "log.jsonl"
        os.environ["FAKE_CACHE_STORE_PATH"] = str(store_path)
        os.environ["FAKE_CACHE_LOG_PATH"] = str(log_path)

        result1 = secret_scanner.scan(repo_root)
        flagged1 = _field(result1, "flagged")
        assert flagged1 is True

        c_py.write_text('K = "removed"\n')

        result2 = secret_scanner.scan(repo_root)
        flagged2 = _field(result2, "flagged")
        assert flagged2 is False

        assert log_path.exists()
        log_lines = [
            json.loads(line)
            for line in log_path.read_text().splitlines()
            if line.strip()
        ]
        assert len(log_lines) == 2

        key1 = log_lines[0]["key"]
        key2 = log_lines[1]["key"]
        assert key1 != key2
        assert log_lines[0]["flagged"] is True
        assert log_lines[1]["flagged"] is False

        final_store = json.loads(store_path.read_text())
        assert key1 in final_store
        assert key2 in final_store

        stored_first_payload = final_store[key1]["payload"]
        stored_first_flagged = _field(stored_first_payload, "flagged")
        assert stored_first_flagged is True

        stored_second_payload = final_store[key2]["payload"]
        stored_second_flagged = _field(stored_second_payload, "flagged")
        assert stored_second_flagged is False
    finally:
        os.environ.clear()
        os.environ.update(old_environ)
        shutil.rmtree(repo_root, ignore_errors=True)
        shutil.rmtree(store_dir, ignore_errors=True)