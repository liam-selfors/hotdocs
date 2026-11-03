import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

import secret_scanner


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


_FAKE_CACHE_MANAGER_SRC = '''
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


def _store_file():
    return os.environ["AC_SECRET_009_STORE_PATH"]


def _log_file():
    return os.environ["AC_SECRET_009_LOG_PATH"]


def _key_str(cache_key):
    return "|".join([
        cache_key.spec_bundle_hash,
        cache_key.gate_inputs_hash,
        cache_key.gate_version,
        cache_key.model_pin,
    ])


def _load_store():
    path = _store_file()
    if os.path.exists(path):
        with open(path, "r") as handle:
            return json.load(handle)
    return {}


def _save_store(store):
    with open(_store_file(), "w") as handle:
        json.dump(store, handle)


def _append_log(entry):
    with open(_log_file(), "a") as handle:
        handle.write(json.dumps(entry) + "\\n")


def get(cache_key, *, repo_root=None):
    store = _load_store()
    key = _key_str(cache_key)
    _append_log({"op": "get", "key": key})
    if key in store:
        return CachedResult(**store[key])
    return Miss()


def put(cache_key, cached_result, *, repo_root=None):
    store = _load_store()
    key = _key_str(cache_key)
    store[key] = {
        "gate_type": cached_result.gate_type,
        "payload": cached_result.payload,
        "stored_at": cached_result.stored_at,
    }
    _save_store(store)
    _append_log({"op": "put", "key": key})
'''


class AcSecret009Test(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.repo_root = Path(self.tmp_dir) / "repo"
        support_dir = Path(self.tmp_dir) / "support"
        (self.repo_root / "gen" / "foo").mkdir(parents=True)
        (self.repo_root / "gen" / "cache-manager").mkdir(parents=True)
        support_dir.mkdir(parents=True)

        self.store_path = support_dir / "store.json"
        self.log_path = support_dir / "log.jsonl"

        (self.repo_root / "gen" / "cache-manager" / "cache_manager.py").write_text(
            _FAKE_CACHE_MANAGER_SRC
        )

        self.target_file = self.repo_root / "gen" / "foo" / "c.py"
        self.target_file.write_text('K = "AKIAABCDEFGHIJKLMNOP"\n')

        self._old_env = {}
        for name, value in (
            ("AC_SECRET_009_STORE_PATH", str(self.store_path)),
            ("AC_SECRET_009_LOG_PATH", str(self.log_path)),
        ):
            self._old_env[name] = os.environ.get(name)
            os.environ[name] = value

    def tearDown(self):
        for name, old_value in self._old_env.items():
            if old_value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = old_value
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _read_log(self):
        if not self.log_path.exists():
            return []
        lines = self.log_path.read_text().splitlines()
        return [json.loads(line) for line in lines if line.strip()]

    def test_flagged_result_survives_clean_rescan_under_its_own_key(self):
        result1 = secret_scanner.scan(self.repo_root)
        self.assertTrue(_get(result1, "flagged"))

        self.target_file.write_text('K = "removed"\n')

        result2 = secret_scanner.scan(self.repo_root)
        self.assertFalse(_get(result2, "flagged"))

        log_entries = self._read_log()
        put_entries = [entry for entry in log_entries if entry["op"] == "put"]
        self.assertEqual(len(put_entries), 2)
        self.assertNotEqual(put_entries[0]["key"], put_entries[1]["key"])

        self.assertTrue(self.store_path.exists())
        store = json.loads(self.store_path.read_text())

        first_key = put_entries[0]["key"]
        second_key = put_entries[1]["key"]

        self.assertIn(first_key, store)
        self.assertIn(second_key, store)

        first_entry = store[first_key]
        second_entry = store[second_key]

        self.assertEqual(_get(first_entry, "gate_type"), "secret_scanner")
        self.assertTrue(_get(_get(first_entry, "payload"), "flagged"))

        self.assertEqual(_get(second_entry, "gate_type"), "secret_scanner")
        self.assertFalse(_get(_get(second_entry, "payload"), "flagged"))


if __name__ == "__main__":
    unittest.main()