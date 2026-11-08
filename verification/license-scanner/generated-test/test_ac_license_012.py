import hashlib
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

import license_scanner


CACHE_MANAGER_MODULE_SOURCE = """
import dataclasses


@dataclasses.dataclass
class CacheKey:
    spec_bundle_hash: str
    gate_inputs_hash: str
    gate_version: str
    model_pin: str


@dataclasses.dataclass
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
"""


def _get(value, name):
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


class LicenseScanAcLicense012Test(unittest.TestCase):
    def setUp(self):
        self._saved_env = dict(os.environ)
        self._tmp_dirs = []

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._saved_env)
        for d in self._tmp_dirs:
            shutil.rmtree(d, ignore_errors=True)

    def _make_repo_root(self):
        repo_root = Path(tempfile.mkdtemp())
        self._tmp_dirs.append(str(repo_root))
        gen_dir = repo_root / "gen" / "foo"
        gen_dir.mkdir(parents=True)
        (gen_dir / "main.py").write_text(
            "def alpha(beta, gamma, delta, epsilon, zeta, eta, theta, iota, kappa):\n"
            "    return beta\n"
        )
        cache_dir = repo_root / "gen" / "cache-manager"
        cache_dir.mkdir(parents=True)
        (cache_dir / "cache_manager.py").write_text(CACHE_MANAGER_MODULE_SOURCE)
        return repo_root

    def test_no_corpus_configured(self):
        os.environ.pop("VAR_LICENSE_CORPUS_PATH", None)
        repo_root = self._make_repo_root()

        result = license_scanner.scan("comp-foo", repo_root)

        self.assertEqual(_get(result, "evaluated"), False)
        self.assertEqual(_get(result, "reason"), "no-reference-corpus")
        self.assertIsNone(_get(result, "similarity_score"))
        self.assertIsNone(_get(result, "block_threshold"))
        self.assertEqual(_get(result, "matches"), [])
        self.assertEqual(_get(result, "blocked"), False)
        self.assertEqual(
            _get(result, "gate_version"),
            "license_scanner@4.0.0-no-reference-corpus",
        )

    def test_corpus_with_empty_entries_is_invalid(self):
        repo_root = self._make_repo_root()
        corpus_path = repo_root / "corpus.json"
        corpus_path.write_text(json.dumps({
            "corpus_version": 1,
            "block_threshold": 0.7,
            "entries": [],
        }))
        os.environ["VAR_LICENSE_CORPUS_PATH"] = str(corpus_path)

        result = license_scanner.scan("comp-foo", repo_root)

        self.assertEqual(_get(result, "evaluated"), False)
        self.assertEqual(_get(result, "reason"), "corpus-invalid")
        self.assertEqual(_get(result, "blocked"), True)
        self.assertIsNone(_get(result, "similarity_score"))
        self.assertIsNone(_get(result, "block_threshold"))
        self.assertEqual(_get(result, "matches"), [])

    def test_valid_corpus_with_no_shared_windows(self):
        repo_root = self._make_repo_root()
        corpus_path = repo_root / "corpus.json"
        unrelated_hash = hashlib.sha256(
            b"unrelated-reference-window-content-that-does-not-appear-anywhere"
        ).hexdigest()
        corpus_version = 3
        corpus_content = {
            "corpus_version": corpus_version,
            "block_threshold": 0.7,
            "entries": [
                {
                    "reference_id": "ref-001",
                    "license_family": "GPL",
                    "risk_tier": "high",
                    "hashes": [unrelated_hash],
                }
            ],
        }
        corpus_bytes = json.dumps(corpus_content).encode("utf-8")
        corpus_path.write_bytes(corpus_bytes)
        os.environ["VAR_LICENSE_CORPUS_PATH"] = str(corpus_path)

        expected_digest = hashlib.sha256(corpus_bytes).hexdigest()[:12]
        expected_gate_version = (
            "license_scanner@4.0." + str(corpus_version) + "+" + expected_digest
        )

        result = license_scanner.scan("comp-foo", repo_root)

        self.assertEqual(_get(result, "evaluated"), True)
        self.assertIsNone(_get(result, "reason"))
        similarity_score = _get(result, "similarity_score")
        self.assertIsNotNone(similarity_score)
        self.assertEqual(similarity_score, 0.0)
        self.assertEqual(_get(result, "blocked"), False)
        self.assertEqual(_get(result, "gate_version"), expected_gate_version)


if __name__ == "__main__":
    unittest.main()