import os
import shutil
import tempfile
import unittest
from pathlib import Path

import secret_scanner


CACHE_MANAGER_SOURCE = """
import dataclasses


@dataclasses.dataclass
class CacheKey:
    spec_bundle_hash: str
    gate_inputs_hash: str
    gate_version: str
    model_pin: str


@dataclasses.dataclass
class CachedResult:
    gate_type: str
    payload: object
    stored_at: str


def get(cache_key, repo_root=None):
    return None


def put(cache_key, cached_result, repo_root=None):
    pass
"""


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _make_repo(path_str):
    repo_root = Path(path_str)
    cache_dir = repo_root / "gen" / "cache-manager"
    cache_dir.mkdir(parents=True, exist_ok=True)
    (cache_dir / "cache_manager.py").write_text(CACHE_MANAGER_SOURCE)
    return repo_root


class ExactlyOneSecretScanResultTest(unittest.TestCase):
    def setUp(self):
        self._old_webhook = os.environ.pop("VAR_COMPLIANCE_WEBHOOK_URL", None)
        self._tmp_dirs = []

    def tearDown(self):
        if self._old_webhook is not None:
            os.environ["VAR_COMPLIANCE_WEBHOOK_URL"] = self._old_webhook
        for d in self._tmp_dirs:
            shutil.rmtree(d, ignore_errors=True)

    def _tmp_repo(self):
        d = tempfile.mkdtemp()
        self._tmp_dirs.append(d)
        return _make_repo(d)

    def test_clean_full_scan_produces_exactly_one_result(self):
        repo_root = self._tmp_repo()
        (repo_root / "readme.txt").write_text(
            "hello world, this is a plain test repository with no secrets.\n"
        )

        result = secret_scanner.scan(repo_root)

        self.assertNotIsInstance(result, (list, tuple, set))
        self.assertTrue(hasattr(result, "to_dict"))

        as_dict = result.to_dict()
        self.assertIsInstance(as_dict, dict)

        for key in (
            "scope",
            "gate_version",
            "flagged",
            "matches",
            "allowed",
            "unused_allowlist_entries",
            "notified",
            "notification_delivery_error",
            "cache_hit",
        ):
            self.assertIn(key, as_dict)

        self.assertEqual(_get(result, "scope"), "full")
        self.assertIsInstance(_get(result, "matches"), list)
        gate_version = _get(result, "gate_version")
        self.assertIsInstance(gate_version, str)
        self.assertTrue(len(gate_version) > 0)

    def test_multi_file_flagged_full_scan_still_produces_exactly_one_result(self):
        repo_root = self._tmp_repo()
        (repo_root / "config_a.py").write_text(
            'AWS_ACCESS_KEY = "AKIAIOSFODNN7EXAMPLE"\n'
        )
        (repo_root / "config_b.py").write_text(
            'AWS_ACCESS_KEY = "AKIAIOSFODNN7EXAMPLE"\n'
        )
        (repo_root / "clean.txt").write_text("no secrets in here at all.\n")

        result = secret_scanner.scan(repo_root)

        # A single scan of a repo with multiple matching files must still
        # yield one SecretScanResult object, not one per file.
        self.assertNotIsInstance(result, (list, tuple, set))
        self.assertTrue(hasattr(result, "to_dict"))

        as_dict = result.to_dict()
        self.assertIsInstance(as_dict, dict)

        matches = _get(result, "matches")
        self.assertIsInstance(matches, list)
        self.assertTrue(_get(result, "flagged"))
        self.assertGreaterEqual(len(matches), 2)

        seen_files = set()
        for match in matches:
            self.assertIsNone(_get(match, "secret_hash"))
            self.assertIsNone(_get(match, "secret_value"))
            match_file = _get(match, "file")
            self.assertIn(match_file, ("config_a.py", "config_b.py"))
            seen_files.add(match_file)

        self.assertEqual(seen_files, {"config_a.py", "config_b.py"})


if __name__ == "__main__":
    unittest.main()