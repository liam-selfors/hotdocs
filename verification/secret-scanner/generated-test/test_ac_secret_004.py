import os
import shutil
import tempfile
import unittest
import unittest.mock
from pathlib import Path

import secret_scanner


def _field(obj, name, default=None):
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


class _FakeResponse:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def getcode(self):
        return 200

    def read(self):
        return b""


AWS_ACCESS_KEY_LINE = 'AWS_ACCESS_KEY_ID = "AKIAIOSFODNN7EXAMPLE"\n'
CLEAN_LINE = 'AWS_ACCESS_KEY_ID = ""\n'
WEBHOOK_VAR = "VAR_COMPLIANCE_WEBHOOK_URL"


class SecretScannerNotificationTest(unittest.TestCase):
    def setUp(self):
        self._prior_webhook = os.environ.get(WEBHOOK_VAR)
        self._tmpdir = tempfile.mkdtemp(prefix="secret-scan-ac004-")

    def tearDown(self):
        shutil.rmtree(self._tmpdir, ignore_errors=True)
        if self._prior_webhook is None:
            os.environ.pop(WEBHOOK_VAR, None)
        else:
            os.environ[WEBHOOK_VAR] = self._prior_webhook

    def test_high_risk_match_notifies_independent_of_later_clean_retry(self):
        os.environ[WEBHOOK_VAR] = "https://compliance.example.invalid/webhook"
        repo_root = Path(self._tmpdir)
        target_file = repo_root / "config.py"
        target_file.write_text(AWS_ACCESS_KEY_LINE)

        calls = []

        def _fake_urlopen(*args, **kwargs):
            calls.append((args, kwargs))
            return _FakeResponse()

        with unittest.mock.patch("urllib.request.urlopen", side_effect=_fake_urlopen):
            result = secret_scanner.scan_files([target_file], repo_root=repo_root)

        flagged = _field(result, "flagged")
        notified = _field(result, "notified")
        matches = _field(result, "matches") or []

        self.assertTrue(flagged)
        self.assertTrue(notified)
        self.assertEqual(len(calls), 1)

        risk_tiers = [_field(m, "risk_tier") for m in matches]
        self.assertIn("high", risk_tiers)

        # a later retry that scans clean never un-notifies the earlier call
        target_file.write_text(CLEAN_LINE)

        with unittest.mock.patch("urllib.request.urlopen", side_effect=_fake_urlopen):
            result2 = secret_scanner.scan_files([target_file], repo_root=repo_root)

        self.assertFalse(_field(result2, "flagged"))
        self.assertFalse(_field(result2, "notified"))
        # the first call's notification remains the only recorded webhook delivery
        self.assertEqual(len(calls), 1)

    def test_no_match_never_calls_urlopen_and_not_notified(self):
        os.environ[WEBHOOK_VAR] = "https://compliance.example.invalid/webhook"
        repo_root = Path(self._tmpdir)
        target_file = repo_root / "clean.py"
        target_file.write_text("x = 1\n")

        calls = []

        def _fake_urlopen(*args, **kwargs):
            calls.append((args, kwargs))
            return _FakeResponse()

        with unittest.mock.patch(
            "urllib.request.urlopen", side_effect=_fake_urlopen
        ) as mock_urlopen:
            result = secret_scanner.scan_files([target_file], repo_root=repo_root)

            self.assertFalse(_field(result, "notified"))
            mock_urlopen.assert_not_called()
        self.assertEqual(len(calls), 0)

    def test_webhook_unset_high_risk_match_flags_but_does_not_notify(self):
        os.environ.pop(WEBHOOK_VAR, None)
        repo_root = Path(self._tmpdir)
        target_file = repo_root / "config.py"
        target_file.write_text(AWS_ACCESS_KEY_LINE)

        calls = []

        def _fake_urlopen(*args, **kwargs):
            calls.append((args, kwargs))
            return _FakeResponse()

        with unittest.mock.patch(
            "urllib.request.urlopen", side_effect=_fake_urlopen
        ) as mock_urlopen:
            result = secret_scanner.scan_files([target_file], repo_root=repo_root)

            self.assertTrue(_field(result, "flagged"))
            self.assertFalse(_field(result, "notified"))
            mock_urlopen.assert_not_called()
        self.assertEqual(len(calls), 0)


if __name__ == "__main__":
    unittest.main()