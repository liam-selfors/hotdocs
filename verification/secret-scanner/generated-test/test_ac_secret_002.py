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


def _invoke_main(argv):
    try:
        result = secret_scanner.main(argv)
    except SystemExit as exc:
        return exc.code
    return result


class TestAcSecret002(unittest.TestCase):
    """AC-SECRET-002: a full scan with at least one match MUST be
    flagged, and the CLI MUST report the merge as blocked (exit 1)."""

    def setUp(self):
        self.repo_root = Path(tempfile.mkdtemp())
        (self.repo_root / "specs").mkdir(parents=True, exist_ok=True)
        (self.repo_root / "verification").mkdir(parents=True, exist_ok=True)
        (self.repo_root / "gen" / "foo-component").mkdir(parents=True, exist_ok=True)

        secret_line = 'API_KEY = "AKIA0123456789ABCDEF"\n'
        (self.repo_root / "gen" / "foo-component" / "config.py").write_text(secret_line)

        patterns_path = self.repo_root / "secret-patterns.json"
        patterns_path.write_text(
            '{"version": "2.0.0", "rules": '
            '[{"rule_id": "aws-access-key-id", "risk_tier": "high", '
            '"pattern": "AKIA[0-9A-Z]{16}"}]}'
        )

        self._old_patterns_path = os.environ.get("VAR_SECRET_PATTERNS_PATH")
        os.environ["VAR_SECRET_PATTERNS_PATH"] = str(patterns_path)

        self._old_webhook_url = os.environ.get("VAR_COMPLIANCE_WEBHOOK_URL")
        os.environ.pop("VAR_COMPLIANCE_WEBHOOK_URL", None)

    def tearDown(self):
        if self._old_patterns_path is None:
            os.environ.pop("VAR_SECRET_PATTERNS_PATH", None)
        else:
            os.environ["VAR_SECRET_PATTERNS_PATH"] = self._old_patterns_path

        if self._old_webhook_url is None:
            os.environ.pop("VAR_COMPLIANCE_WEBHOOK_URL", None)
        else:
            os.environ["VAR_COMPLIANCE_WEBHOOK_URL"] = self._old_webhook_url

        shutil.rmtree(self.repo_root, ignore_errors=True)

    def test_full_scan_with_match_flags_true_and_blocks_merge(self):
        result = secret_scanner.scan(self.repo_root)

        self.assertEqual(_get(result, "scope"), "full")

        matches = _get(result, "matches")
        self.assertTrue(matches, "expected at least one match in the fixture")

        self.assertTrue(
            _get(result, "flagged"),
            "a full scan with at least one match MUST set flagged to true",
        )

        exit_code = _invoke_main(
            ["--repo-root=" + str(self.repo_root), "--format=json"]
        )
        self.assertEqual(
            exit_code,
            1,
            "a flagged full scan MUST report the merge as blocked via exit code 1",
        )


if __name__ == "__main__":
    unittest.main()