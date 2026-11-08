import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path

import license_scanner


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _get(value, key, default=None):
    if isinstance(value, dict):
        return value.get(key, default)
    return getattr(value, key, default)


class TestACLicense009(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo_root = Path(self._tmp.name)

        cache_manager_src = '''
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


class _Miss:
    payload = None


def get(cache_key, *, repo_root=None):
    return _Miss()


def put(cache_key, result, *, repo_root=None):
    return None
'''
        _write(
            self.repo_root / "gen" / "cache-manager" / "cache_manager.py",
            cache_manager_src,
        )

        tokens = ["tok{}".format(i) for i in range(1, 11)]
        source_text = " ".join(tokens) + "\n"
        _write(self.repo_root / "gen" / "foo" / "foo.py", source_text)

        window_tokens = tokens[0:9]
        window_hash = hashlib.sha256(
            "\x1f".join(window_tokens).encode("utf-8")
        ).hexdigest()

        corpus = {
            "corpus_version": 1,
            "block_threshold": 0.70,
            "entries": [
                {
                    "reference_id": "ref-001",
                    "license_family": "GPL",
                    "risk_tier": "high",
                    "hashes": [window_hash],
                }
            ],
        }
        corpus_path = self.repo_root / "license-corpus.json"
        _write(corpus_path, json.dumps(corpus))

        self._env_patches = {
            "VAR_LICENSE_CORPUS_PATH": "license-corpus.json",
            "VAR_COMPLIANCE_WEBHOOK_URL": "http://127.0.0.1:1/unreachable-webhook",
        }
        self._old_env = {}
        for key, value in self._env_patches.items():
            self._old_env[key] = os.environ.get(key)
            os.environ[key] = value

    def tearDown(self):
        for key, old in self._old_env.items():
            if old is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = old
        self._tmp.cleanup()

    def test_high_risk_match_webhook_network_error_sets_notified_and_delivery_error(self):
        result = license_scanner.scan("comp-foo", self.repo_root)

        evaluated = _get(result, "evaluated")
        self.assertTrue(evaluated)
        self.assertIsNone(_get(result, "reason"))

        matches = _get(result, "matches") or []
        risk_tiers = [_get(m, "risk_tier") for m in matches]
        self.assertIn("high", risk_tiers)

        blocked = _get(result, "blocked")
        self.assertFalse(blocked)

        notified = _get(result, "notified")
        self.assertTrue(notified)

        delivery_error = _get(result, "notification_delivery_error")
        self.assertIsNotNone(delivery_error)

        category = _get(delivery_error, "category")
        self.assertEqual(category, "network")

        message = _get(delivery_error, "message")
        self.assertTrue(isinstance(message, str) and len(message) > 0)


if __name__ == "__main__":
    unittest.main()