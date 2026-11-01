import hashlib
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

import license_scanner


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


_FAKE_CACHE_MANAGER_SOURCE = '''
from dataclasses import dataclass


@dataclass
class CacheKey:
    spec_bundle_hash: str
    gate_inputs_hash: str
    gate_version: str
    model_pin: str


@dataclass
class CachedResult:
    gate_type: str
    payload: dict
    stored_at: str


class Miss:
    pass


def get(cache_key, *, repo_root=None):
    return Miss()


def put(cache_key, result, *, repo_root=None):
    return None
'''


class AcLicense008Test(unittest.TestCase):
    def setUp(self):
        self.repo_root = tempfile.mkdtemp(prefix="hotdocs-ac-license-008-")
        self._prev_corpus_path = os.environ.get("VAR_LICENSE_CORPUS_PATH")

    def tearDown(self):
        shutil.rmtree(self.repo_root, ignore_errors=True)
        if self._prev_corpus_path is None:
            os.environ.pop("VAR_LICENSE_CORPUS_PATH", None)
        else:
            os.environ["VAR_LICENSE_CORPUS_PATH"] = self._prev_corpus_path

    def test_shared_eight_token_run_contributes_no_matching_window_hash(self):
        component_slug = "sample-component"
        component_id = "comp-" + component_slug

        component_dir = os.path.join(self.repo_root, "gen", component_slug)
        os.makedirs(component_dir, exist_ok=True)

        # 10 tokens -> exactly two 9-token windows, neither equal to the
        # reference window below (shifted by one position each way), while
        # tokens[1:9] ("alpha".."hotel") are the same 8-token run as the
        # reference window's first 8 tokens.
        gen_source = "zulu alpha bravo charlie delta echo foxtrot golf hotel yankee\n"
        with open(os.path.join(component_dir, "main.py"), "w", encoding="utf-8") as f:
            f.write(gen_source)

        reference_tokens = [
            "alpha", "bravo", "charlie", "delta",
            "echo", "foxtrot", "golf", "hotel", "india",
        ]
        reference_hash = hashlib.sha256(
            "\x1f".join(reference_tokens).encode("utf-8")
        ).hexdigest()

        corpus = {
            "corpus_version": 1,
            "block_threshold": 0.70,
            "entries": [
                {
                    "reference_id": "ref-ac-license-008",
                    "license_family": "test-family",
                    "risk_tier": "low",
                    "hashes": [reference_hash],
                }
            ],
        }
        corpus_dir = os.path.join(self.repo_root, "corpus")
        os.makedirs(corpus_dir, exist_ok=True)
        corpus_path = os.path.join(corpus_dir, "license_corpus.json")
        with open(corpus_path, "w", encoding="utf-8") as f:
            json.dump(corpus, f)
        os.environ["VAR_LICENSE_CORPUS_PATH"] = corpus_path

        cache_manager_dir = os.path.join(self.repo_root, "gen", "cache-manager")
        os.makedirs(cache_manager_dir, exist_ok=True)
        with open(
            os.path.join(cache_manager_dir, "cache_manager.py"), "w", encoding="utf-8"
        ) as f:
            f.write(_FAKE_CACHE_MANAGER_SOURCE)

        result = license_scanner.scan(component_id, Path(self.repo_root))

        similarity_score = _get(result, "similarity_score")
        blocked = _get(result, "blocked")
        matches = _get(result, "matches", [])
        cache_hit = _get(result, "cache_hit")

        self.assertEqual(similarity_score, 0.0)
        self.assertFalse(blocked)
        self.assertFalse(cache_hit)
        self.assertEqual(list(matches), [])


if __name__ == "__main__":
    unittest.main()