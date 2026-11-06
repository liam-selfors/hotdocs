import hashlib
import json
import os
import re
import tempfile
import unittest
from pathlib import Path

import license_scanner


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _write_fake_cache_manager(repo_root):
    cache_dir = repo_root / "gen" / "cache-manager"
    cache_dir.mkdir(parents=True, exist_ok=True)
    (cache_dir / "cache_manager.py").write_text(
        '''
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


def get(cache_key, *, repo_root=None):
    return {"gate_type": None, "payload": None, "stored_at": None}


def put(cache_key, result, *, repo_root=None):
    pass
''',
        encoding="utf-8",
    )


_TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*|\d+")


def _tokenize(text):
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.DOTALL)
    text = re.sub(r'""".*?"""', " ", text, flags=re.DOTALL)
    text = re.sub(r"'''.*?'''", " ", text, flags=re.DOTALL)
    text = re.sub(r"//.*", "", text)
    text = re.sub(r"#.*", "", text)
    return [tok.lower() for tok in _TOKEN_RE.findall(text)]


def _window_hashes(tokens, size=9):
    hashes = []
    for i in range(len(tokens) - size + 1):
        window = "\x1f".join(tokens[i:i + size])
        hashes.append(hashlib.sha256(window.encode("utf-8")).hexdigest())
    return hashes


class TestACLicense001(unittest.TestCase):
    def test_similarity_at_block_threshold_blocks_merge(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            _write_fake_cache_manager(repo_root)

            component_id = "comp-widget"
            slug = "widget"
            component_dir = repo_root / "gen" / slug
            component_dir.mkdir(parents=True, exist_ok=True)

            source_text = (
                "# a line comment that must be stripped\n"
                "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu\n"
            )
            (component_dir / "widget.py").write_text(source_text, encoding="utf-8")

            tokens = _tokenize(source_text)
            window_hashes = sorted(set(_window_hashes(tokens, 9)))
            self.assertTrue(len(window_hashes) > 0)

            corpus = {
                "corpus_version": 7,
                "block_threshold": 0.5,
                "entries": [
                    {
                        "reference_id": "ref-001",
                        "license_family": "gpl-3.0",
                        "risk_tier": "high",
                        "hashes": window_hashes,
                    }
                ],
            }
            corpus_path = repo_root / "corpus.json"
            corpus_path.write_text(json.dumps(corpus), encoding="utf-8")

            old_env = os.environ.get("VAR_LICENSE_CORPUS_PATH")
            os.environ["VAR_LICENSE_CORPUS_PATH"] = str(corpus_path)
            try:
                result = license_scanner.scan(component_id, repo_root)
            finally:
                if old_env is None:
                    os.environ.pop("VAR_LICENSE_CORPUS_PATH", None)
                else:
                    os.environ["VAR_LICENSE_CORPUS_PATH"] = old_env

            self.assertTrue(_get(result, "evaluated"))
            self.assertIsNone(_get(result, "reason"))

            similarity_score = _get(result, "similarity_score")
            block_threshold = _get(result, "block_threshold")
            self.assertIsNotNone(similarity_score)
            self.assertIsNotNone(block_threshold)
            self.assertGreaterEqual(similarity_score, block_threshold)

            self.assertTrue(_get(result, "blocked"))

            matches = _get(result, "matches")
            self.assertTrue(matches)
            match0 = matches[0]
            self.assertEqual(_get(match0, "reference_id"), "ref-001")
            self.assertEqual(_get(match0, "license_family"), "gpl-3.0")
            self.assertEqual(_get(match0, "risk_tier"), "high")


if __name__ == "__main__":
    unittest.main()