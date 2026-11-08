import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path


def get_field(obj, name, default=None):
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


FAKE_CACHE_MANAGER_SOURCE = r"""
import dataclasses
import json
import os

STORE_PATH = os.environ["FAKE_CACHE_STORE_PATH"]
LOG_PATH = os.environ["FAKE_CACHE_LOG_PATH"]


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


def _key_str(cache_key):
    return "|".join([
        cache_key.spec_bundle_hash,
        cache_key.gate_inputs_hash,
        cache_key.gate_version,
        cache_key.model_pin,
    ])


def _load_store():
    if os.path.exists(STORE_PATH):
        with open(STORE_PATH, "r") as f:
            return json.load(f)
    return {}


def _save_store(store):
    with open(STORE_PATH, "w") as f:
        json.dump(store, f)


def _log(op, key):
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps({"op": op, "key": key}) + "\n")


def get(cache_key, *, repo_root=None):
    store = _load_store()
    k = _key_str(cache_key)
    _log("get", k)
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
        "gate_type": result.gate_type,
        "payload": result.payload,
        "stored_at": result.stored_at,
    }
    _save_store(store)
    _log("put", k)
"""


def sha256_window(tokens):
    return hashlib.sha256("\x1f".join(tokens).encode("utf-8")).hexdigest()


FLAGGED_TOKENS = ["alpha", "beta", "gamma", "delta", "epsilon", "zeta", "eta", "theta", "iota"]
CLEAN_TOKENS = ["zebra", "yolk", "xray", "wobble", "vortex", "umbra", "tango", "sierra", "romeo"]


class TestACLicense007(unittest.TestCase):
    def setUp(self):
        self._saved_env = {}
        for key in ("VAR_LICENSE_CORPUS_PATH", "FAKE_CACHE_STORE_PATH", "FAKE_CACHE_LOG_PATH"):
            self._saved_env[key] = os.environ.get(key)

    def tearDown(self):
        for key, value in self._saved_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_flagged_attempt_preserved_when_retry_scans_clean(self):
        with tempfile.TemporaryDirectory() as repo_root_str, \
             tempfile.TemporaryDirectory() as side_dir_str:

            repo_root = Path(repo_root_str)
            side_dir = Path(side_dir_str)

            cache_manager_dir = repo_root / "gen" / "cache-manager"
            cache_manager_dir.mkdir(parents=True)
            (cache_manager_dir / "cache_manager.py").write_text(FAKE_CACHE_MANAGER_SOURCE)

            component_dir = repo_root / "gen" / "widget"
            component_dir.mkdir(parents=True)
            source_file = component_dir / "widget.py"
            source_file.write_text(" ".join(FLAGGED_TOKENS))

            flagged_hash = sha256_window(FLAGGED_TOKENS)
            corpus = {
                "corpus_version": 1,
                "block_threshold": 0.70,
                "entries": [
                    {
                        "reference_id": "ref-100",
                        "license_family": "GPL-3.0",
                        "risk_tier": "high",
                        "hashes": [flagged_hash],
                    }
                ],
            }
            corpus_path = side_dir / "corpus.json"
            corpus_path.write_text(json.dumps(corpus))

            store_path = side_dir / "store.json"
            log_path = side_dir / "log.jsonl"

            os.environ["VAR_LICENSE_CORPUS_PATH"] = str(corpus_path)
            os.environ["FAKE_CACHE_STORE_PATH"] = str(store_path)
            os.environ["FAKE_CACHE_LOG_PATH"] = str(log_path)

            import license_scanner

            component_id = "comp-widget"

            result1 = license_scanner.scan(component_id, repo_root)
            evaluated1 = get_field(result1, "evaluated")
            blocked1 = get_field(result1, "blocked")
            score1 = get_field(result1, "similarity_score")

            self.assertTrue(evaluated1)
            self.assertTrue(blocked1)
            self.assertEqual(score1, 1.0)

            source_file.write_text(" ".join(CLEAN_TOKENS))

            result2 = license_scanner.scan(component_id, repo_root)
            evaluated2 = get_field(result2, "evaluated")
            blocked2 = get_field(result2, "blocked")
            score2 = get_field(result2, "similarity_score")

            self.assertTrue(evaluated2)
            self.assertFalse(blocked2)
            self.assertEqual(score2, 0.0)

            self.assertTrue(store_path.exists())
            with open(store_path) as f:
                store = json.load(f)

            license_entries = [
                entry for entry in store.values()
                if get_field(entry, "gate_type") == "license_scanner"
            ]
            self.assertEqual(
                len(license_entries), 2,
                "expected two distinct cache-manager records (flagged and clean), "
                "got %r" % (license_entries,)
            )

            flagged_payloads = [
                get_field(entry, "payload") for entry in license_entries
                if get_field(get_field(entry, "payload"), "blocked") is True
            ]
            clean_payloads = [
                get_field(entry, "payload") for entry in license_entries
                if get_field(get_field(entry, "payload"), "blocked") is False
            ]

            self.assertEqual(
                len(flagged_payloads), 1,
                "the original flagged LicenseScanResult must still be present in the record"
            )
            self.assertEqual(
                len(clean_payloads), 1,
                "the clean LicenseScanResult from the retried scan must be present in the record"
            )

            flagged_payload = flagged_payloads[0]
            self.assertEqual(get_field(flagged_payload, "component_id"), component_id)
            self.assertTrue(get_field(flagged_payload, "matches"))

            self.assertTrue(log_path.exists())
            with open(log_path) as f:
                log_lines = [json.loads(line) for line in f if line.strip()]

            put_ops = [entry for entry in log_lines if get_field(entry, "op") == "put"]
            self.assertGreaterEqual(
                len(put_ops), 2,
                "the fake cache-manager's put() must have been invoked for both attempts"
            )
            self.assertNotEqual(
                get_field(put_ops[0], "key"),
                get_field(put_ops[-1], "key"),
                "the retried clean attempt must not reuse (and thereby overwrite) "
                "the original flagged attempt's cache key"
            )


if __name__ == "__main__":
    unittest.main()