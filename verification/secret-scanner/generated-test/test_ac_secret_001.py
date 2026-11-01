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


def _write_pattern_db(repo_root, filename="secret-patterns.json"):
    db = {
        "version": "2.0.0",
        "rules": [
            {
                "rule_id": "aws-access-key-id",
                "risk_tier": "high",
                "pattern": "AKIA[0-9A-Z]{16}",
            }
        ],
    }
    (repo_root / filename).write_text(json.dumps(db))
    return filename


class SecretScanFullScanTest(unittest.TestCase):
    def setUp(self):
        self.repo_root = Path(tempfile.mkdtemp())
        (self.repo_root / "specs").mkdir(parents=True, exist_ok=True)
        (self.repo_root / "gen").mkdir(parents=True, exist_ok=True)
        (self.repo_root / "verification").mkdir(parents=True, exist_ok=True)

        self._saved_env = {}
        for name in ("VAR_SECRET_PATTERNS_PATH", "VAR_COMPLIANCE_WEBHOOK_URL"):
            self._saved_env[name] = os.environ.pop(name, None)

    def tearDown(self):
        shutil.rmtree(self.repo_root, ignore_errors=True)
        for name, value in self._saved_env.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value

    def test_file_with_known_api_key_shape_is_reported_in_matches(self):
        pattern_file = _write_pattern_db(self.repo_root)
        os.environ["VAR_SECRET_PATTERNS_PATH"] = pattern_file

        gen_dir = self.repo_root / "gen" / "foo"
        gen_dir.mkdir(parents=True, exist_ok=True)
        (gen_dir / "config.py").write_text('API_KEY = "AKIAABCDEFGHIJKLMNOP"\n')

        result = secret_scanner.scan(self.repo_root)

        matches = _get(result, "matches")
        matched_entry = None
        for m in matches:
            if _get(m, "file") == "gen/foo/config.py":
                matched_entry = m
                break

        self.assertIsNotNone(
            matched_entry,
            f"expected gen/foo/config.py to be reported in matches, got: {matches}",
        )
        self.assertEqual(_get(matched_entry, "rule_id"), "aws-access-key-id")

    def test_pycache_dir_and_non_utf8_file_are_skipped(self):
        pattern_file = _write_pattern_db(self.repo_root)
        os.environ["VAR_SECRET_PATTERNS_PATH"] = pattern_file

        pycache_dir = self.repo_root / "gen" / "foo" / "__pycache__"
        pycache_dir.mkdir(parents=True, exist_ok=True)
        (pycache_dir / "x.txt").write_text("AKIAABCDEFGHIJKLMNOP\n")

        foo_dir = self.repo_root / "gen" / "foo"
        foo_dir.mkdir(parents=True, exist_ok=True)
        (foo_dir / "blob.bin").write_bytes(
            b"AKIAABCDEFGHIJKLMNOP" + b"\xff\xfe\x00\x01"
        )

        result = secret_scanner.scan(self.repo_root)

        self.assertFalse(_get(result, "flagged"))
        self.assertEqual(_get(result, "matches"), [])


if __name__ == "__main__":
    unittest.main()