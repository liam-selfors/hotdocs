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


_STALE_MATCH = {
    "rule_id": "AWS Access Key",
    "risk_tier": "high",
    "file": "nonexistent/stale.py",
    "line": 7,
}

_FAKE_CACHE_MANAGER_SRC = '''
import json
import os
from dataclasses import dataclass
from typing import Any


@dataclass
class CacheKey:
    spec_bundle_hash: str
    gate_inputs_hash: str
    gate_version: str
    model_pin: str


@dataclass
class CachedResult:
    gate_type: str
    payload: Any
    stored_at: str


_STORED_PAYLOAD = {
    "scope": "full",
    "gate_version": "secret_scanner@3.1.0+detect-secrets.1.5.0",
    "flagged": True,
    "matches": [
        {
            "rule_id": "AWS Access Key",
            "risk_tier": "high",
            "file": "nonexistent/stale.py",
            "line": 7,
        }
    ],
    "allowed": [],
    "unused_allowlist_entries": [],
    "notified": False,
    "notification_delivery_error": None,
    "cache_hit": False,
}


def _log(event):
    path = os.environ["AC_SECRET_005_CALL_LOG"]
    with open(path, "a") as f:
        f.write(json.dumps(event) + "\\n")


def get(cache_key, *, repo_root=None):
    _log({"op": "get"})
    return CachedResult(
        gate_type="secret_scanner",
        payload=dict(_STORED_PAYLOAD),
        stored_at="2026-01-01T00:00:00Z",
    )


def put(cache_key, result, *, repo_root=None):
    _log({"op": "put"})
'''


class TestAcSecret005(unittest.TestCase):
    def setUp(self):
        self.repo_root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.repo_root, ignore_errors=True)

        log_dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, log_dir, ignore_errors=True)
        self.call_log = log_dir / "calls.jsonl"

        self._old_env = os.environ.get("AC_SECRET_005_CALL_LOG")
        os.environ["AC_SECRET_005_CALL_LOG"] = str(self.call_log)
        self.addCleanup(self._restore_env)

        specs_dir = self.repo_root / "specs"
        specs_dir.mkdir(parents=True)
        (specs_dir / "overview.md").write_text("Nothing secret in here.\n")

        src_dir = self.repo_root / "src"
        src_dir.mkdir(parents=True)
        (src_dir / "app.py").write_text(
            "def greet():\n    return 'hello'\n"
        )

        cache_dir = self.repo_root / "gen" / "cache-manager"
        cache_dir.mkdir(parents=True)
        (cache_dir / "cache_manager.py").write_text(_FAKE_CACHE_MANAGER_SRC)

    def _restore_env(self):
        if self._old_env is None:
            os.environ.pop("AC_SECRET_005_CALL_LOG", None)
        else:
            os.environ["AC_SECRET_005_CALL_LOG"] = self._old_env

    def _read_call_log(self):
        if not self.call_log.exists():
            return []
        return [
            json.loads(line)
            for line in self.call_log.read_text().splitlines()
            if line.strip()
        ]

    def test_cache_hit_returns_cached_matches_without_calling_put(self):
        result = secret_scanner.scan(self.repo_root)

        calls = self._read_call_log()
        get_calls = [c for c in calls if c["op"] == "get"]
        put_calls = [c for c in calls if c["op"] == "put"]

        self.assertEqual(len(get_calls), 1)
        self.assertEqual(len(put_calls), 0)

        self.assertTrue(_get(result, "cache_hit"))

        matches = _get(result, "matches")
        self.assertEqual(matches, [dict(_STALE_MATCH)])

        # A fresh scan of src/app.py (no secrets) would never have
        # produced this match, confirming the cached result -- not a
        # rescan of the current files -- is what was returned.
        self.assertNotEqual(
            {m["file"] for m in matches},
            {"src/app.py"},
        )


if __name__ == "__main__":
    unittest.main()