import os
import shutil
import tempfile
import unittest
import urllib.request
from pathlib import Path

import secret_scanner


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


class TestAcSecret004b(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.repo_root = Path(self.tmp)
        foo_dir = self.repo_root / "gen" / "foo"
        foo_dir.mkdir(parents=True)
        (foo_dir / "h.py").write_text(
            'sha = "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b"\n'
        )

        self._old_webhook = os.environ.get("VAR_COMPLIANCE_WEBHOOK_URL")
        os.environ["VAR_COMPLIANCE_WEBHOOK_URL"] = "https://example.invalid/hook"

        self._old_urlopen = urllib.request.urlopen
        self.calls = []

        def recorder(*args, **kwargs):
            self.calls.append((args, kwargs))

            class _Response:
                status = 200

                def __enter__(self):
                    return self

                def __exit__(self, exc_type, exc_val, exc_tb):
                    return False

                def read(self):
                    return b"{}"

            return _Response()

        urllib.request.urlopen = recorder

    def tearDown(self):
        urllib.request.urlopen = self._old_urlopen
        if self._old_webhook is None:
            os.environ.pop("VAR_COMPLIANCE_WEBHOOK_URL", None)
        else:
            os.environ["VAR_COMPLIANCE_WEBHOOK_URL"] = self._old_webhook
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_low_risk_blocking_match_still_notifies_once(self):
        result = secret_scanner.scan(self.repo_root)

        flagged = _get(result, "flagged")
        matches = _get(result, "matches")

        self.assertTrue(flagged)
        self.assertIsNotNone(matches)

        h_matches = [
            m for m in matches
            if _get(m, "file", "").replace("\\", "/") == "gen/foo/h.py"
        ]
        self.assertTrue(
            len(h_matches) >= 1,
            "expected at least one match for gen/foo/h.py, got: %r" % (matches,),
        )
        self.assertTrue(
            any(_get(m, "risk_tier") == "low" for m in h_matches),
            "expected a low risk_tier match for gen/foo/h.py, got: %r" % (h_matches,),
        )

        self.assertEqual(
            len(self.calls), 1,
            "expected the compliance webhook recorder to be called exactly once",
        )


if __name__ == "__main__":
    unittest.main()