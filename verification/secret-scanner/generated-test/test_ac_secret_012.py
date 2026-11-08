import os
import shutil
import tempfile
import textwrap
import unittest
from pathlib import Path

import secret_scanner


CACHE_MANAGER_SOURCE = textwrap.dedent(r'''
    import dataclasses
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


    def _log(event):
        path = os.environ.get("STANDIN_CALL_LOG")
        if path:
            with open(path, "a") as f:
                f.write(event + "\n")


    def get(cache_key, repo_root=None):
        _log("get")
        return Miss()


    def put(cache_key, result, repo_root=None):
        _log("put")
        return None
    ''')


def _write_cache_manager_standin(repo_root):
    cache_dir = os.path.join(str(repo_root), "gen", "cache-manager")
    os.makedirs(cache_dir, exist_ok=True)
    with open(os.path.join(cache_dir, "cache_manager.py"), "w") as f:
        f.write(CACHE_MANAGER_SOURCE)


def _snapshot(repo_root):
    snapshot = {}
    for dirpath, _dirnames, filenames in os.walk(str(repo_root)):
        for name in filenames:
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, str(repo_root))
            with open(full, "rb") as f:
                snapshot[rel] = f.read()
    return snapshot


def _field(value, name):
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


class GateVersionMatchesScanTest(unittest.TestCase):
    def setUp(self):
        self.repo_root = Path(tempfile.mkdtemp(prefix="secret-scanner-ac012-"))
        _write_cache_manager_standin(self.repo_root)
        self._old_log = os.environ.get("STANDIN_CALL_LOG")
        os.environ.pop("STANDIN_CALL_LOG", None)

    def tearDown(self):
        shutil.rmtree(str(self.repo_root), ignore_errors=True)
        if self._old_log is None:
            os.environ.pop("STANDIN_CALL_LOG", None)
        else:
            os.environ["STANDIN_CALL_LOG"] = self._old_log

    def test_gate_version_matches_scan_result(self):
        version_from_gate = secret_scanner.gate_version(self.repo_root)
        scan_result = secret_scanner.scan(self.repo_root)
        version_from_scan = _field(scan_result, "gate_version")

        self.assertIsInstance(version_from_gate, str)
        self.assertEqual(version_from_gate, version_from_scan)


class GateVersionDoesNotScanOrTouchCacheTest(unittest.TestCase):
    def setUp(self):
        self.repo_root = Path(tempfile.mkdtemp(prefix="secret-scanner-ac012-"))
        _write_cache_manager_standin(self.repo_root)

        secret_file = os.path.join(str(self.repo_root), "config.py")
        with open(secret_file, "w") as f:
            f.write('AWS_KEY = "AKIAIOSFODNN7EXAMPLE"\n')

        log_dir = tempfile.mkdtemp(prefix="secret-scanner-ac012-log-")
        self.addCleanup(shutil.rmtree, log_dir, ignore_errors=True)
        self.call_log_path = os.path.join(log_dir, "calls.log")

        self._old_log = os.environ.get("STANDIN_CALL_LOG")
        os.environ["STANDIN_CALL_LOG"] = self.call_log_path

    def tearDown(self):
        shutil.rmtree(str(self.repo_root), ignore_errors=True)
        if self._old_log is None:
            os.environ.pop("STANDIN_CALL_LOG", None)
        else:
            os.environ["STANDIN_CALL_LOG"] = self._old_log

    def test_gate_version_is_pure_and_skips_cache(self):
        before = _snapshot(self.repo_root)
        result = secret_scanner.gate_version(self.repo_root)
        after = _snapshot(self.repo_root)

        self.assertIsInstance(result, str)
        self.assertFalse(os.path.exists(self.call_log_path))
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()