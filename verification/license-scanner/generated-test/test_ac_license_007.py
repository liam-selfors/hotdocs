"""Test for AC-LICENSE-007 against comp-license-scanner.

Scope note: comp-license-scanner's own documented interface never
mentions `.hotdocs/attempts/` (R-LICENSE-007's actual preservation
mechanism lives in a different, undocumented-here component). The
only persistence this component's contract exposes is its
cache-manager interaction, so that is what this test exercises: a
flagged attempt and a later clean retry must land in two distinct,
non-colliding cache entries rather than one overwriting the other.
"""

import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

import license_scanner


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


FAKE_CACHE_MANAGER_SOURCE = """
import dataclasses
import json
import os


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


class Miss:
    pass


_STORE_PATH = os.environ["FAKE_CACHE_STORE_PATH"]


def _read_store():
    if not os.path.exists(_STORE_PATH):
        return []
    with open(_STORE_PATH, "r") as f:
        return json.load(f)


def _write_store(entries):
    with open(_STORE_PATH, "w") as f:
        json.dump(entries, f)


def _key_list(cache_key):
    return [
        cache_key.spec_bundle_hash,
        cache_key.gate_inputs_hash,
        cache_key.gate_version,
        cache_key.model_pin,
    ]


def get(cache_key, *, repo_root=None):
    entries = _read_store()
    kl = _key_list(cache_key)
    for entry in entries:
        if entry["key"] == kl:
            return CachedResult(
                gate_type=entry["gate_type"],
                payload=entry["payload"],
                stored_at=entry["stored_at"],
            )
    return Miss()


def put(cache_key, result, *, repo_root=None):
    entries = _read_store()
    kl = _key_list(cache_key)
    entries = [e for e in entries if e["key"] != kl]
    entries.append(
        {
            "key": kl,
            "gate_type": result.gate_type,
            "payload": result.payload,
            "stored_at": result.stored_at,
        }
    )
    _write_store(entries)
"""


class LicenseScannerPreservesFlaggedAttemptTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo_root = Path(self._tmp.name)

        cache_manager_dir = self.repo_root / "gen" / "cache-manager"
        cache_manager_dir.mkdir(parents=True)
        (cache_manager_dir / "cache_manager.py").write_text(
            FAKE_CACHE_MANAGER_SOURCE
        )

        self.store_path = self.repo_root / "fake_cache_store.json"
        self.corpus_path = self.repo_root / "license-corpus.json"

        self.flagged_tokens = [
            "alpha",
            "beta",
            "gamma",
            "delta",
            "epsilon",
            "zeta",
            "eta",
            "theta",
            "iota",
        ]
        window = "\x1f".join(self.flagged_tokens)
        flagged_hash = hashlib.sha256(window.encode("utf-8")).hexdigest()

        corpus = {
            "corpus_version": 3,
            "block_threshold": 0.70,
            "entries": [
                {
                    "reference_id": "ref-001",
                    "license_family": "GPL",
                    "risk_tier": "high",
                    "hashes": [flagged_hash],
                }
            ],
        }
        self.corpus_path.write_text(json.dumps(corpus))

        self.widget_dir = self.repo_root / "gen" / "widget"
        self.widget_dir.mkdir(parents=True)
        self.widget_file = self.widget_dir / "widget.py"
        self.widget_file.write_text(" ".join(self.flagged_tokens) + "\n")

        env_updates = {
            "VAR_LICENSE_CORPUS_PATH": str(self.corpus_path),
            "FAKE_CACHE_STORE_PATH": str(self.store_path),
        }
        self._old_env = {}
        for key, value in env_updates.items():
            self._old_env[key] = os.environ.get(key)
            os.environ[key] = value
        for absent_key in ("VAR_COMPLIANCE_WEBHOOK_URL",):
            self._old_env.setdefault(absent_key, os.environ.get(absent_key))
            os.environ.pop(absent_key, None)

    def tearDown(self):
        for key, old_value in self._old_env.items():
            if old_value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = old_value
        sys.modules.pop("cache_manager", None)
        self._tmp.cleanup()

    def test_flagged_attempt_preserved_after_clean_retry(self):
        flagged_result = license_scanner.scan("comp-widget", self.repo_root)

        self.assertTrue(_get(flagged_result, "blocked"))
        self.assertGreaterEqual(_get(flagged_result, "similarity_score"), 0.70)
        flagged_matches = _get(flagged_result, "matches") or []
        self.assertTrue(
            any(_get(m, "reference_id") == "ref-001" for m in flagged_matches)
        )

        clean_tokens = [
            "red",
            "green",
            "blue",
            "purple",
            "orange",
            "yellow",
            "black",
            "white",
            "gray",
            "pink",
        ]
        self.widget_file.write_text(" ".join(clean_tokens) + "\n")

        clean_result = license_scanner.scan("comp-widget", self.repo_root)
        self.assertFalse(_get(clean_result, "blocked"))

        self.assertTrue(self.store_path.exists())
        entries = json.loads(self.store_path.read_text())

        payloads = [entry["payload"] for entry in entries]
        blocked_payloads = [p for p in payloads if _get(p, "blocked") is True]
        clean_payloads = [p for p in payloads if _get(p, "blocked") is False]

        self.assertEqual(
            len(blocked_payloads),
            1,
            "the original flagged result must still be present, exactly once",
        )
        self.assertEqual(
            len(clean_payloads),
            1,
            "the clean retry result must also be present",
        )

        preserved_flagged = blocked_payloads[0]
        self.assertEqual(_get(preserved_flagged, "component_id"), "comp-widget")
        self.assertGreaterEqual(_get(preserved_flagged, "similarity_score"), 0.70)
        preserved_matches = _get(preserved_flagged, "matches") or []
        self.assertTrue(
            any(_get(m, "reference_id") == "ref-001" for m in preserved_matches),
            "the flagged entry's own matches must not have been erased or overwritten",
        )

        preserved_clean = clean_payloads[0]
        self.assertEqual(_get(preserved_clean, "component_id"), "comp-widget")


if __name__ == "__main__":
    unittest.main()