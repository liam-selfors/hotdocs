import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

import secret_scanner


FAKE_CACHE_MANAGER_SOURCE = '''
import json
import os
from dataclasses import dataclass


@dataclass
class CacheKey:
    spec_bundle_hash: str
    gate_inputs_hash: str
    gate_version: str
    model_pin: str


@dataclass
class CachedResult:
    gate_type: str
    payload: dict
    stored_at: str


class Miss:
    pass


def get(cache_key, repo_root=None):
    return Miss()


def put(cache_key, result, repo_root=None):
    log_path = os.environ.get("AC_SECRET_003_LOG_PATH")
    if not log_path:
        return
    gate_type = result.gate_type if hasattr(result, "gate_type") else result.get("gate_type")
    payload = result.payload if hasattr(result, "payload") else result.get("payload")
    with open(log_path, "a") as handle:
        handle.write(json.dumps({"gate_type": gate_type, "payload": payload}) + "\\n")
'''


def _field(value, key):
    if isinstance(value, dict):
        return value.get(key)
    return getattr(value, key, None)


class AcSecret003Test(unittest.TestCase):
    def setUp(self):
        self.repo_root = Path(tempfile.mkdtemp(prefix="ac_secret_003_repo_"))
        (self.repo_root / "README.md").write_text(
            "This repository contains no secret material of any kind.\n"
        )

        cache_manager_dir = self.repo_root / "gen" / "cache-manager"
        cache_manager_dir.mkdir(parents=True)
        (cache_manager_dir / "cache_manager.py").write_text(FAKE_CACHE_MANAGER_SOURCE)

        self._log_dir = tempfile.mkdtemp(prefix="ac_secret_003_log_")
        self.log_path = Path(self._log_dir) / "put_calls.jsonl"
        self._prev_log_env = os.environ.get("AC_SECRET_003_LOG_PATH")
        os.environ["AC_SECRET_003_LOG_PATH"] = str(self.log_path)

    def tearDown(self):
        shutil.rmtree(self.repo_root, ignore_errors=True)
        shutil.rmtree(self._log_dir, ignore_errors=True)
        if self._prev_log_env is None:
            os.environ.pop("AC_SECRET_003_LOG_PATH", None)
        else:
            os.environ["AC_SECRET_003_LOG_PATH"] = self._prev_log_env

    def test_clean_full_scan_is_still_recorded(self):
        result = secret_scanner.scan(self.repo_root)

        self.assertIsNotNone(result)
        self.assertEqual(_field(result, "scope"), "full")
        self.assertEqual(_field(result, "flagged"), False)
        self.assertEqual(_field(result, "matches"), [])

        self.assertTrue(self.log_path.exists())
        lines = [line for line in self.log_path.read_text().splitlines() if line.strip()]
        self.assertEqual(len(lines), 1)

        record = json.loads(lines[0])
        self.assertEqual(_field(record, "gate_type"), "secret_scanner")

        payload = record["payload"]
        self.assertEqual(_field(payload, "scope"), "full")
        self.assertEqual(_field(payload, "flagged"), False)
        self.assertEqual(_field(payload, "matches"), [])
        self.assertIsNotNone(_field(payload, "gate_version"))


if __name__ == "__main__":
    unittest.main()