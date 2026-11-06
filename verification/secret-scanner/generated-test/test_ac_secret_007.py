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


class TestAcSecret007(unittest.TestCase):
    def setUp(self):
        self.repo_root = Path(tempfile.mkdtemp(prefix="secret_scan_ac007_"))
        self._old_webhook = os.environ.pop("VAR_COMPLIANCE_WEBHOOK_URL", None)

    def tearDown(self):
        shutil.rmtree(self.repo_root, ignore_errors=True)
        if self._old_webhook is not None:
            os.environ["VAR_COMPLIANCE_WEBHOOK_URL"] = self._old_webhook

    def test_full_scan_with_multiple_flagged_files_yields_one_result(self):
        (self.repo_root / "README.md").write_text("Nothing interesting here.\n")

        nested = self.repo_root / "src" / "config"
        nested.mkdir(parents=True)
        aws_key_line = 'AWS_KEY = "AKIAIOSFODNN7EXAMPLE"\n'
        (self.repo_root / "config_a.py").write_text(aws_key_line)
        (nested / "config_b.py").write_text(aws_key_line)

        result = secret_scanner.scan(self.repo_root)

        self.assertNotIsInstance(result, (list, tuple, set))

        to_dict = getattr(result, "to_dict", None)
        self.assertTrue(callable(to_dict), "SecretScanResult must expose to_dict()")
        payload = result.to_dict()
        self.assertIsInstance(payload, dict)

        self.assertEqual(_get(payload, "scope"), "full")
        self.assertIn("matches", payload)
        self.assertIn("allowed", payload)
        self.assertIn("unused_allowlist_entries", payload)
        self.assertIn("notified", payload)
        self.assertIn("notification_delivery_error", payload)
        self.assertIn("cache_hit", payload)

        matches = _get(payload, "matches")
        self.assertIsInstance(matches, list)
        # Two files each contain the planted key: a single SecretScanResult
        # must aggregate both findings rather than one result per file/match.
        self.assertGreaterEqual(len(matches), 2)

        self.assertTrue(_get(payload, "flagged"))

    def test_scan_called_twice_each_returns_its_own_single_result(self):
        (self.repo_root / "clean.txt").write_text("no secrets at all\n")

        first = secret_scanner.scan(self.repo_root)
        second = secret_scanner.scan(self.repo_root)

        for result in (first, second):
            self.assertNotIsInstance(result, (list, tuple, set))
            to_dict = getattr(result, "to_dict", None)
            self.assertTrue(callable(to_dict))
            payload = result.to_dict()
            self.assertIsInstance(payload, dict)
            self.assertEqual(_get(payload, "scope"), "full")


if __name__ == "__main__":
    unittest.main()