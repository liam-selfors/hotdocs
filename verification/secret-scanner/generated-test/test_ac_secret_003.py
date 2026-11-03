import shutil
import tempfile
import unittest
from pathlib import Path

import secret_scanner


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


class TestAcSecret003(unittest.TestCase):
    """AC-SECRET-003 / R-SECRET-003: a clean full scan still yields a
    complete SecretScanResult record, not an omitted/empty one."""

    def setUp(self):
        self.repo_root = Path(tempfile.mkdtemp(prefix="ac_secret_003_"))
        (self.repo_root / "clean_module.py").write_text(
            "def add(a, b):\n    return a + b\n"
        )
        (self.repo_root / "README.md").write_text(
            "This is a clean fixture repository with no secrets.\n"
        )

    def tearDown(self):
        shutil.rmtree(self.repo_root, ignore_errors=True)

    def test_clean_full_scan_still_produces_full_result_record(self):
        result = secret_scanner.scan(self.repo_root)

        # A clean outcome MUST still be a real, present result object -
        # never None or otherwise omitted.
        self.assertIsNotNone(result)

        self.assertFalse(_get(result, "flagged"))
        self.assertEqual(_get(result, "matches"), [])

        self.assertTrue(hasattr(result, "to_dict"))
        payload = result.to_dict()
        self.assertIsInstance(payload, dict)

        required_keys = (
            "scope",
            "gate_version",
            "flagged",
            "matches",
            "allowed",
            "unused_allowlist_entries",
            "notified",
            "notification_delivery_error",
            "cache_hit",
        )
        for key in required_keys:
            self.assertIn(
                key,
                payload,
                "clean SecretScanResult.to_dict() must still carry %r; "
                "absence of a flag must not mean absence of a record" % key,
            )

        self.assertEqual(payload["scope"], "full")
        self.assertTrue(payload["gate_version"])
        self.assertFalse(payload["flagged"])
        self.assertEqual(payload["matches"], [])
        self.assertFalse(payload["notified"])
        self.assertIsNone(payload["notification_delivery_error"])
        self.assertFalse(payload["cache_hit"])


if __name__ == "__main__":
    unittest.main()