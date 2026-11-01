import json
import os
import shutil
import tempfile
import unittest
import urllib.request
from pathlib import Path


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


CACHE_MANAGER_MODULE_SOURCE = '''
import os


class CacheKey:
    def __init__(self, spec_bundle_hash, gate_inputs_hash, gate_version, model_pin):
        self.spec_bundle_hash = spec_bundle_hash
        self.gate_inputs_hash = gate_inputs_hash
        self.gate_version = gate_version
        self.model_pin = model_pin


class CachedResult:
    def __init__(self, gate_type, payload, stored_at):
        self.gate_type = gate_type
        self.payload = payload
        self.stored_at = stored_at


_CACHED_PAYLOAD = {
    "scope": "full",
    "gate_version": "secret_scanner@2.0.0",
    "flagged": True,
    "matches": [
        {
            "rule_id": "aws-access-key-id",
            "risk_tier": "high",
            "file": "specs/fake-cached-match.txt",
            "line": 1,
        }
    ],
    "notified": False,
    "notification_delivery_error": None,
    "cache_hit": False,
}


def _log(event):
    log_path = os.environ.get("FAKE_CACHE_MANAGER_LOG")
    if log_path:
        with open(log_path, "a") as f:
            f.write(event + "\\n")


def get(cache_key, *, repo_root=None):
    _log("get")
    return CachedResult(
        gate_type="secret_scanner",
        payload=dict(_CACHED_PAYLOAD),
        stored_at="2026-01-01T00:00:00Z",
    )


def put(cache_key, result, *, repo_root=None):
    _log("put")
    return None
'''


class AcSecret005Test(unittest.TestCase):
    def setUp(self):
        self.repo_root = Path(tempfile.mkdtemp(prefix="hotdocs-secretscan-"))
        self.addCleanup(shutil.rmtree, self.repo_root, ignore_errors=True)

        log_dir = Path(tempfile.mkdtemp(prefix="hotdocs-log-"))
        self.addCleanup(shutil.rmtree, log_dir, ignore_errors=True)
        self.log_file = log_dir / "invocations.log"

        patterns_dir = Path(tempfile.mkdtemp(prefix="hotdocs-patterns-"))
        self.addCleanup(shutil.rmtree, patterns_dir, ignore_errors=True)
        patterns_path = patterns_dir / "patterns.json"
        patterns_path.write_text(
            json.dumps(
                {
                    "version": "2.0.0",
                    "rules": [
                        {
                            "rule_id": "aws-access-key-id",
                            "risk_tier": "high",
                            "pattern": "AKIA[0-9A-Z]{16}",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

        self._old_environ = dict(os.environ)
        os.environ["FAKE_CACHE_MANAGER_LOG"] = str(self.log_file)
        os.environ["VAR_SECRET_PATTERNS_PATH"] = str(patterns_path)
        os.environ.pop("VAR_COMPLIANCE_WEBHOOK_URL", None)

        for sub in ("specs", "gen", "verification"):
            (self.repo_root / sub).mkdir(parents=True, exist_ok=True)

        # A would-be match at a different file/line than the cached
        # one below -- proves a cache hit does not rescan.
        (self.repo_root / "specs" / "real-secret.txt").write_text(
            "AKIAABCDEFGHIJKLMNOP\n", encoding="utf-8"
        )

        cache_manager_dir = self.repo_root / "gen" / "cache-manager"
        cache_manager_dir.mkdir(parents=True, exist_ok=True)
        (cache_manager_dir / "cache_manager.py").write_text(
            CACHE_MANAGER_MODULE_SOURCE, encoding="utf-8"
        )

        self._old_urlopen = urllib.request.urlopen

        def _fail_urlopen(*args, **kwargs):
            raise AssertionError("urlopen must not be called on a cache hit")

        urllib.request.urlopen = _fail_urlopen
        self.addCleanup(self._restore_urlopen)

    def _restore_urlopen(self):
        urllib.request.urlopen = self._old_urlopen

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._old_environ)

    def test_cache_hit_returns_cached_matches_and_skips_put(self):
        import secret_scanner

        result = secret_scanner.scan(self.repo_root)

        self.assertTrue(_get(result, "cache_hit"))
        self.assertEqual(_get(result, "scope"), "full")
        self.assertTrue(_get(result, "flagged"))
        self.assertEqual(_get(result, "notified"), False)
        self.assertIsNone(_get(result, "notification_delivery_error"))

        matches = _get(result, "matches")
        self.assertEqual(len(matches), 1)
        match = matches[0]
        self.assertEqual(_get(match, "rule_id"), "aws-access-key-id")
        self.assertEqual(_get(match, "risk_tier"), "high")
        self.assertEqual(_get(match, "file"), "specs/fake-cached-match.txt")
        self.assertEqual(_get(match, "line"), 1)

        self.assertTrue(
            all(_get(m, "file") != "specs/real-secret.txt" for m in matches)
        )

        self.assertTrue(self.log_file.exists())
        log_lines = self.log_file.read_text(encoding="utf-8").splitlines()
        self.assertIn("get", log_lines)
        self.assertNotIn("put", log_lines)


if __name__ == "__main__":
    unittest.main()