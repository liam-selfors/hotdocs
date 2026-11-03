import os
import tempfile
import unittest
from pathlib import Path

import secret_scanner


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


class TestAcSecret010(unittest.TestCase):
    def setUp(self):
        self._webhook_var = "VAR_COMPLIANCE_WEBHOOK_URL"
        self._had_webhook_var = self._webhook_var in os.environ
        self._old_webhook_value = os.environ.pop(self._webhook_var, None)

    def tearDown(self):
        if self._had_webhook_var:
            os.environ[self._webhook_var] = self._old_webhook_value

    def test_quoted_secrets_yield_two_low_risk_matches(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            target = repo_root / "gen" / "foo" / "e.py"
            target.parent.mkdir(parents=True)
            target.write_text(
                'token = "aB3dE5gH7jK9mN1pQ3sT5vW7yZ9bD1fH3jL5nP7r"\n'
                'sha = "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b"\n'
            )

            result = secret_scanner.scan(repo_root)
            matches = _get(result, "matches", [])

            self.assertEqual(len(matches), 2)

            first = matches[0]
            self.assertEqual(_get(first, "rule_id"), "Base64 High Entropy String")
            self.assertEqual(_get(first, "risk_tier"), "low")
            self.assertEqual(_get(first, "file"), "gen/foo/e.py")
            self.assertEqual(_get(first, "line"), 1)

            second = matches[1]
            self.assertEqual(_get(second, "rule_id"), "Hex High Entropy String")
            self.assertEqual(_get(second, "risk_tier"), "low")
            self.assertEqual(_get(second, "file"), "gen/foo/e.py")
            self.assertEqual(_get(second, "line"), 2)

            for match in matches:
                self.assertIsNone(_get(match, "secret"))
                self.assertIsNone(_get(match, "secret_hash"))
                self.assertIsNone(_get(match, "hashed_secret"))

    def test_unquoted_secret_is_a_known_gap_and_yields_no_matches(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            target = repo_root / "gen" / "foo" / "e.py"
            target.parent.mkdir(parents=True)
            target.write_text(
                "token = aB3dE5gH7jK9mN1pQ3sT5vW7yZ9bD1fH3jL5nP7r\n"
            )

            result = secret_scanner.scan(repo_root)
            matches = _get(result, "matches", [])

            self.assertEqual(matches, [])


if __name__ == "__main__":
    unittest.main()