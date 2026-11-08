import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

import license_scanner


FAKE_CACHE_MANAGER_SOURCE = '''
import dataclasses
import json
from pathlib import Path


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


def _f(obj, name):
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


def _key_string(cache_key):
    parts = [
        _f(cache_key, "spec_bundle_hash"),
        _f(cache_key, "gate_inputs_hash"),
        _f(cache_key, "gate_version"),
        _f(cache_key, "model_pin"),
    ]
    return "\\x1e".join(str(p) for p in parts)


def _store_path(repo_root):
    return Path(repo_root) / "_fake_cache_store.json"


def _log_path(repo_root):
    return Path(repo_root) / "_fake_cache_log.jsonl"


def _load_store(repo_root):
    p = _store_path(repo_root)
    if p.exists():
        return json.loads(p.read_text())
    return {}


def _save_store(repo_root, data):
    _store_path(repo_root).write_text(json.dumps(data))


def _append_log(repo_root, record):
    with open(_log_path(repo_root), "a") as f:
        f.write(json.dumps(record) + "\\n")


def get(cache_key, *, repo_root=None):
    data = _load_store(repo_root)
    k = _key_string(cache_key)
    gv = _f(cache_key, "gate_version")
    if k in data:
        entry = data[k]
        _append_log(repo_root, {"op": "get", "gate_version": gv, "result": "hit"})
        return CachedResult(
            gate_type=entry["gate_type"],
            payload=entry["payload"],
            stored_at=entry["stored_at"],
        )
    _append_log(repo_root, {"op": "get", "gate_version": gv, "result": "miss"})
    return Miss()


def put(cache_key, result, *, repo_root=None):
    data = _load_store(repo_root)
    k = _key_string(cache_key)
    gv = _f(cache_key, "gate_version")
    data[k] = {
        "gate_type": _f(result, "gate_type"),
        "payload": _f(result, "payload"),
        "stored_at": _f(result, "stored_at"),
    }
    _save_store(repo_root, data)
    _append_log(repo_root, {"op": "put", "gate_version": gv})
'''


def _field(obj, name):
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


class TestACLicense005(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="ac-license-005-")
        self.repo_root = Path(self._tmp)
        self._old_env = os.environ.get("VAR_LICENSE_CORPUS_PATH")

        cache_dep_dir = self.repo_root / "gen" / "cache-manager"
        cache_dep_dir.mkdir(parents=True, exist_ok=True)
        (cache_dep_dir / "cache_manager.py").write_text(FAKE_CACHE_MANAGER_SOURCE)

        component_dir = self.repo_root / "gen" / "widget"
        component_dir.mkdir(parents=True, exist_ok=True)
        (component_dir / "main.py").write_text(
            "def greet(name):\n    return 'hello ' + name\n"
        )

        self.corpus_path = self.repo_root / "reference_corpus.json"

    def tearDown(self):
        if self._old_env is None:
            os.environ.pop("VAR_LICENSE_CORPUS_PATH", None)
        else:
            os.environ["VAR_LICENSE_CORPUS_PATH"] = self._old_env
        shutil.rmtree(self._tmp, ignore_errors=True)

    def _write_corpus(self, version, token):
        corpus = {
            "corpus_version": version,
            "block_threshold": 0.70,
            "entries": [
                {
                    "reference_id": "ref-001",
                    "license_family": "GPL",
                    "risk_tier": "high",
                    "hashes": [token * 8],
                }
            ],
        }
        self.corpus_path.write_text(json.dumps(corpus))

    def _log_records(self):
        log_path = self.repo_root / "_fake_cache_log.jsonl"
        if not log_path.exists():
            return []
        return [
            json.loads(line)
            for line in log_path.read_text().splitlines()
            if line.strip()
        ]

    def test_corpus_update_invalidates_stale_cache_entry(self):
        os.environ["VAR_LICENSE_CORPUS_PATH"] = str(self.corpus_path)

        # Given: a cached result exists under the gate_version for corpus v1.
        self._write_corpus(1, "a")
        gate_version_v1 = license_scanner.gate_version(self.repo_root)
        self.assertTrue(gate_version_v1.startswith("license_scanner@4.0.1+"))

        first_result = license_scanner.scan("comp-widget", self.repo_root)
        self.assertEqual(_field(first_result, "gate_version"), gate_version_v1)
        self.assertTrue(_field(first_result, "evaluated"))
        self.assertFalse(_field(first_result, "cache_hit"))

        store_path = self.repo_root / "_fake_cache_store.json"
        self.assertTrue(store_path.exists())
        store = json.loads(store_path.read_text())
        self.assertEqual(len(store), 1)
        stale_key = next(iter(store))

        # Corrupt the stored payload with sentinel values a fresh scan
        # against the current corpus would never produce, so reuse of
        # this stale entry is unmistakably detectable.
        store[stale_key]["payload"]["blocked"] = True
        store[stale_key]["payload"]["similarity_score"] = 0.999
        store[stale_key]["payload"]["matches"] = [
            {
                "reference_id": "STALE-SENTINEL",
                "license_family": "stale",
                "risk_tier": "high",
                "score": 0.999,
            }
        ]
        store_path.write_text(json.dumps(store))

        # And: the reference corpus is updated to a new version.
        self._write_corpus(2, "b")
        gate_version_v2 = license_scanner.gate_version(self.repo_root)
        self.assertTrue(gate_version_v2.startswith("license_scanner@4.0.2+"))
        self.assertNotEqual(gate_version_v2, gate_version_v1)

        # When: license-scan runs with the new gate_version.
        second_result = license_scanner.scan("comp-widget", self.repo_root)

        # Then: the stale cache entry is not reused and a fresh scan is performed.
        self.assertEqual(_field(second_result, "gate_version"), gate_version_v2)
        self.assertNotEqual(_field(second_result, "gate_version"), gate_version_v1)
        self.assertTrue(_field(second_result, "evaluated"))
        self.assertFalse(_field(second_result, "cache_hit"))

        matches = _field(second_result, "matches") or []
        match_ids = [_field(m, "reference_id") for m in matches]
        self.assertNotIn("STALE-SENTINEL", match_ids)
        self.assertNotEqual(_field(second_result, "similarity_score"), 0.999)

        records = self._log_records()
        get_v2_records = [
            r for r in records if r["op"] == "get" and r["gate_version"] == gate_version_v2
        ]
        self.assertTrue(get_v2_records)
        self.assertEqual(get_v2_records[-1]["result"], "miss")

        put_gate_versions = {r["gate_version"] for r in records if r["op"] == "put"}
        self.assertIn(gate_version_v1, put_gate_versions)
        self.assertIn(gate_version_v2, put_gate_versions)

        final_store = json.loads(store_path.read_text())
        self.assertEqual(len(final_store), 2)
        self.assertIn(stale_key, final_store)
        self.assertEqual(
            final_store[stale_key]["payload"]["matches"][0]["reference_id"],
            "STALE-SENTINEL",
        )


if __name__ == "__main__":
    unittest.main()