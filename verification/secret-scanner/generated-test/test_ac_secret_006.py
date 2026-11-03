import importlib.metadata
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


FAKE_CACHE_MANAGER_SOURCE = """
import dataclasses
import json
import os


_LOG_PATH = os.environ.get("AC_SECRET_006_LOG")
_OLD_GATE_VERSION = "secret_scanner@0.0.1+detect-secrets.0.0.0"


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


class _Miss:
    payload = None


def _log(event, cache_key):
    if not _LOG_PATH:
        return
    with open(_LOG_PATH, "a") as handle:
        print(
            json.dumps({"event": event, "gate_version": cache_key.gate_version}),
            file=handle,
        )


def get(cache_key, repo_root=None):
    _log("get", cache_key)
    if cache_key.gate_version == _OLD_GATE_VERSION:
        return CachedResult(
            gate_type="secret_scanner",
            payload={
                "scope": "full",
                "gate_version": _OLD_GATE_VERSION,
                "flagged": True,
                "matches": [
                    {
                        "rule_id": "stale-cached-match",
                        "risk_tier": "high",
                        "file": "stale.py",
                        "line": 1,
                    }
                ],
                "allowed": [],
                "unused_allowlist_entries": [],
                "notified": False,
                "notification_delivery_error": None,
                "cache_hit": True,
            },
            stored_at="2020-01-01T00:00:00Z",
        )
    return _Miss()


def put(cache_key, cached_result, repo_root=None):
    _log("put", cache_key)
"""


class TestAcSecret006(unittest.TestCase):
    def test_gate_version_matches_installed_detect_secrets_version(self):
        repo_root = Path(tempfile.mkdtemp())
        try:
            (repo_root / "README.txt").write_text("hello world\n")

            installed_version = importlib.metadata.version("detect-secrets")
            expected_gate_version = (
                "secret_scanner@3.0.0+detect-secrets." + installed_version
            )

            reported = secret_scanner.gate_version(repo_root)
            self.assertEqual(reported, expected_gate_version)

            result = secret_scanner.scan(repo_root)
            self.assertEqual(_get(result, "gate_version"), expected_gate_version)
        finally:
            shutil.rmtree(repo_root, ignore_errors=True)

    def test_mismatched_cached_gate_version_is_not_reused(self):
        repo_root = Path(tempfile.mkdtemp())
        log_dir = Path(tempfile.mkdtemp())
        log_path = log_dir / "invocations.log"
        try:
            (repo_root / "README.txt").write_text("hello world\n")

            cache_manager_dir = repo_root / "gen" / "cache-manager"
            cache_manager_dir.mkdir(parents=True)
            (cache_manager_dir / "cache_manager.py").write_text(
                FAKE_CACHE_MANAGER_SOURCE
            )

            previous_log_env = os.environ.get("AC_SECRET_006_LOG")
            os.environ["AC_SECRET_006_LOG"] = str(log_path)
            try:
                result = secret_scanner.scan(repo_root)
            finally:
                if previous_log_env is None:
                    os.environ.pop("AC_SECRET_006_LOG", None)
                else:
                    os.environ["AC_SECRET_006_LOG"] = previous_log_env

            installed_version = importlib.metadata.version("detect-secrets")
            expected_gate_version = (
                "secret_scanner@3.0.0+detect-secrets." + installed_version
            )

            matches = _get(result, "matches") or []
            match_rule_ids = [_get(match, "rule_id") for match in matches]
            self.assertNotIn("stale-cached-match", match_rule_ids)
            self.assertFalse(_get(result, "flagged"))
            self.assertFalse(_get(result, "cache_hit"))
            self.assertEqual(_get(result, "gate_version"), expected_gate_version)

            self.assertTrue(log_path.exists())
            events = [
                json.loads(line)
                for line in log_path.read_text().splitlines()
                if line.strip()
            ]
            event_names = [event["event"] for event in events]
            self.assertIn("get", event_names)
            self.assertIn("put", event_names)
        finally:
            shutil.rmtree(repo_root, ignore_errors=True)
            shutil.rmtree(log_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()