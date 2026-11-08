import hashlib
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

import license_scanner


def _field(obj, name):
    return obj.get(name) if isinstance(obj, dict) else getattr(obj, name, None)


class TestACLicense002CleanResultRecorded(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.repo_root = Path(self.tmpdir) / "repo"
        self.repo_root.mkdir()
        self.component_id = "comp-sample-widget"
        self.slug = "sample-widget"
        self._env_backup = {}

    def tearDown(self):
        for key, value in self._env_backup.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _set_env(self, key, value):
        self._env_backup[key] = os.environ.get(key)
        os.environ[key] = value

    def test_clean_scan_result_is_fully_populated_and_recorded(self):
        # gen/<slug>/ content with no match against the reference corpus
        gen_dir = self.repo_root / "gen" / self.slug
        gen_dir.mkdir(parents=True)
        source = (
            "def alpha_bravo_charlie(delta, echo, foxtrot, golf, hotel, india, juliet):\n"
            "    return delta + echo + foxtrot + golf + hotel + india + juliet\n"
        )
        (gen_dir / "widget.py").write_text(source, encoding="utf-8")

        # a usable reference corpus whose hashes can never equal a real sha256
        # hex digest of any 9-token window from the source above
        corpus_version = 3
        corpus = {
            "corpus_version": corpus_version,
            "block_threshold": 0.70,
            "entries": [
                {
                    "reference_id": "ref-001",
                    "license_family": "GPL",
                    "risk_tier": "high",
                    "hashes": ["not-a-real-hash-1", "not-a-real-hash-2"],
                }
            ],
        }
        corpus_bytes = json.dumps(corpus).encode("utf-8")
        corpus_path = self.repo_root / "license-corpus.json"
        corpus_path.write_bytes(corpus_bytes)
        expected_hash_prefix = hashlib.sha256(corpus_bytes).hexdigest()[:12]
        expected_gate_version = (
            f"license_scanner@4.0.{corpus_version}+{expected_hash_prefix}"
        )
        self._set_env("VAR_LICENSE_CORPUS_PATH", str(corpus_path))

        # fake cache-manager dependency: flat module, always a miss, and logs
        # every put() call (with its full payload) to a file this test controls
        cache_mgr_dir = self.repo_root / "gen" / "cache-manager"
        cache_mgr_dir.mkdir(parents=True)
        put_log_path = Path(self.tmpdir) / "put_log.jsonl"
        self._set_env("TEST_LICENSE_SCANNER_PUT_LOG", str(put_log_path))

        fake_module_source = '''
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


def get(cache_key, *, repo_root=None):
    return Miss()


def put(cache_key, result, *, repo_root=None):
    log_path = os.environ.get("TEST_LICENSE_SCANNER_PUT_LOG")
    if not log_path:
        return
    record = {"gate_type": result.gate_type, "payload": result.payload}
    with open(log_path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\\n")
'''
        (cache_mgr_dir / "cache_manager.py").write_text(
            fake_module_source, encoding="utf-8"
        )

        result = license_scanner.scan(self.component_id, self.repo_root)

        self.assertIsNotNone(result)

        self.assertEqual(_field(result, "component_id"), self.component_id)
        self.assertEqual(_field(result, "gate_version"), expected_gate_version)
        self.assertTrue(_field(result, "evaluated"))
        self.assertIsNone(_field(result, "reason"))

        similarity_score = _field(result, "similarity_score")
        self.assertIsNotNone(similarity_score)
        self.assertEqual(similarity_score, 0.0)

        block_threshold = _field(result, "block_threshold")
        self.assertEqual(block_threshold, 0.70)

        self.assertFalse(_field(result, "blocked"))

        matches = _field(result, "matches")
        self.assertIsNotNone(matches)
        self.assertEqual(matches, [])

        self.assertFalse(_field(result, "notified"))
        self.assertIsNone(_field(result, "notification_delivery_error"))
        self.assertFalse(_field(result, "cache_hit"))

        # the clean result must still be handed in full to the recording
        # layer, never skipped or omitted just because it was clean
        self.assertTrue(put_log_path.exists())
        lines = put_log_path.read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(len(lines), 1)
        record = json.loads(lines[0])
        self.assertEqual(record["gate_type"], "license_scanner")
        payload = record["payload"]
        self.assertEqual(payload["component_id"], self.component_id)
        self.assertEqual(payload["gate_version"], expected_gate_version)
        self.assertEqual(payload["blocked"], False)
        self.assertEqual(payload["matches"], [])
        self.assertIn("similarity_score", payload)
        self.assertEqual(payload["similarity_score"], 0.0)


if __name__ == "__main__":
    unittest.main()