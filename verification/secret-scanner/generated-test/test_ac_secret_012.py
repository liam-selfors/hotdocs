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


_FAKE_CACHE_MANAGER_SOURCE = '''
import os


def _record(name):
    record_file = os.environ.get("TEST_CACHE_MANAGER_RECORD_FILE")
    if record_file:
        with open(record_file, "a") as handle:
            handle.write(name + "\\n")


class CacheKey:
    def __init__(self, spec_bundle_hash=None, gate_inputs_hash=None,
                 gate_version=None, model_pin=None):
        _record("CacheKey")
        self.spec_bundle_hash = spec_bundle_hash
        self.gate_inputs_hash = gate_inputs_hash
        self.gate_version = gate_version
        self.model_pin = model_pin


class CachedResult:
    def __init__(self, gate_type=None, payload=None, stored_at=None):
        _record("CachedResult")
        self.gate_type = gate_type
        self.payload = payload
        self.stored_at = stored_at


def get(cache_key, *, repo_root=None):
    _record("get")
    return None


def put(cache_key, result, *, repo_root=None):
    _record("put")
    return None
'''


class TestGateVersionMatchesScan(unittest.TestCase):

    def setUp(self):
        self._env_backup = {
            "VAR_SECRET_PATTERNS_PATH": os.environ.get("VAR_SECRET_PATTERNS_PATH"),
        }

    def tearDown(self):
        for key, value in self._env_backup.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def _make_repo_root(self):
        repo_root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, repo_root, ignore_errors=True)
        (repo_root / "specs").mkdir(parents=True, exist_ok=True)
        (repo_root / "gen").mkdir(parents=True, exist_ok=True)
        (repo_root / "verification").mkdir(parents=True, exist_ok=True)
        return repo_root

    def _write_pattern_db(self, repo_root, version, rel_path="patterns.json"):
        db_path = repo_root / rel_path
        db_path.write_text(json.dumps({"version": version, "rules": []}))
        return db_path

    def test_gate_version_matches_scan_result_and_changes_with_version(self):
        repo_root = self._make_repo_root()
        self._write_pattern_db(repo_root, "7")
        os.environ["VAR_SECRET_PATTERNS_PATH"] = "patterns.json"

        gv_first = secret_scanner.gate_version(repo_root)
        scan_result_first = secret_scanner.scan(repo_root)
        scan_gate_version_first = _get(scan_result_first, "gate_version")

        self.assertEqual(gv_first, scan_gate_version_first)

        self._write_pattern_db(repo_root, "8")
        gv_second = secret_scanner.gate_version(repo_root)

        self.assertNotEqual(gv_second, gv_first)

    def test_gate_version_matches_scan_result_when_var_unset(self):
        repo_root = self._make_repo_root()
        os.environ.pop("VAR_SECRET_PATTERNS_PATH", None)

        gv = secret_scanner.gate_version(repo_root)
        scan_result = secret_scanner.scan(repo_root)
        scan_gate_version = _get(scan_result, "gate_version")

        self.assertEqual(gv, scan_gate_version)

    def test_gate_version_never_calls_cache_manager(self):
        repo_root = self._make_repo_root()
        os.environ.pop("VAR_SECRET_PATTERNS_PATH", None)

        record_file = repo_root.parent / ("cache_manager_record_" + repo_root.name + ".log")
        self.addCleanup(lambda: record_file.unlink(missing_ok=True))
        os.environ["TEST_CACHE_MANAGER_RECORD_FILE"] = str(record_file)
        self.addCleanup(os.environ.pop, "TEST_CACHE_MANAGER_RECORD_FILE", None)

        dep_dir = repo_root / "gen" / "cache-manager"
        dep_dir.mkdir(parents=True, exist_ok=True)
        module_path = dep_dir / "cache_manager.py"
        module_path.write_text(_FAKE_CACHE_MANAGER_SOURCE)

        result = secret_scanner.gate_version(repo_root)

        self.assertIsInstance(result, str)
        self.assertTrue(len(result) > 0)
        self.assertFalse(record_file.exists())


if __name__ == "__main__":
    unittest.main()