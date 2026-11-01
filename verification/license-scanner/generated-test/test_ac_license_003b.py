import hashlib
import json
import os
import re
import tempfile
import unittest
from pathlib import Path

import license_scanner


_COMMENT_RE = re.compile(
    r'/\*.*?\*/|""".*?"""|\'\'\'.*?\'\'\'|//[^\n]*|#[^\n]*', re.DOTALL
)
_TOKEN_RE = re.compile(r'[A-Za-z_][A-Za-z0-9_]*|\d+')


def _tokenize(text):
    stripped = _COMMENT_RE.sub(' ', text)
    return [tok.lower() for tok in _TOKEN_RE.findall(stripped)]


def _window_hashes(tokens, size=9):
    hashes = []
    for i in range(len(tokens) - size + 1):
        window = tokens[i:i + size]
        joined = '\x1f'.join(window)
        hashes.append(hashlib.sha256(joined.encode('utf-8')).hexdigest())
    return hashes


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


_CACHE_MANAGER_SOURCE = '''
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
    payload: object
    stored_at: str


class Miss:
    pass


def get(cache_key, *, repo_root=None):
    return Miss()


def put(cache_key, result, *, repo_root=None):
    pass
'''


class AcLicense003bTest(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.repo_root = Path(self._tmpdir.name)

        self._set_env('VAR_LICENSE_CORPUS_PATH', 'corpus/license_corpus.json')
        # Port 1 is reliably closed locally, so the webhook attempt fails
        # fast without ever reaching a real network destination.
        self._set_env('VAR_COMPLIANCE_WEBHOOK_URL', 'http://127.0.0.1:1/webhook')

        cache_manager_dir = self.repo_root / 'gen' / 'cache-manager'
        cache_manager_dir.mkdir(parents=True, exist_ok=True)
        (cache_manager_dir / 'cache_manager.py').write_text(_CACHE_MANAGER_SOURCE)

        component_dir = self.repo_root / 'gen' / 'foo'
        component_dir.mkdir(parents=True, exist_ok=True)
        source_text = 'alpha beta gamma delta epsilon zeta eta theta iota kappa'
        (component_dir / 'foo.py').write_text(source_text)

        tokens = _tokenize(source_text)
        hashes = _window_hashes(tokens)
        # Ten tokens -> exactly two distinct 9-token windows.
        self.assertEqual(len(hashes), 2)

        corpus_dir = self.repo_root / 'corpus'
        corpus_dir.mkdir(parents=True, exist_ok=True)
        corpus = {
            'corpus_version': 1,
            'block_threshold': 0.70,
            'entries': [
                {
                    'reference_id': 'ref-001',
                    'license_family': 'GPL',
                    'risk_tier': 'high',
                    # Only one of the two distinct windows is present in
                    # this entry, so the component's score against it is
                    # exactly 1/2 -- below the 0.70 block threshold.
                    'hashes': [hashes[0]],
                }
            ],
        }
        (corpus_dir / 'license_corpus.json').write_text(json.dumps(corpus))

    def _set_env(self, name, value):
        previous = os.environ.get(name)
        os.environ[name] = value

        def _restore():
            if previous is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = previous

        self.addCleanup(_restore)

    def test_below_block_threshold_high_risk_tier_notifies_without_blocking(self):
        result = license_scanner.scan('comp-foo', self.repo_root)

        similarity_score = _get(result, 'similarity_score')
        block_threshold = _get(result, 'block_threshold')
        blocked = _get(result, 'blocked')
        notified = _get(result, 'notified')
        matches = _get(result, 'matches') or []

        self.assertIsNotNone(similarity_score)
        self.assertIsNotNone(block_threshold)
        # Given: a similarity score below the block threshold.
        self.assertLess(similarity_score, block_threshold)

        # Given: ... against a reference entry with risk_tier "high".
        high_risk_match_present = any(
            _get(match, 'risk_tier') == 'high' for match in matches
        )
        self.assertTrue(
            high_risk_match_present,
            'expected a reported match with risk_tier "high"',
        )

        # Then: blocked is false but notified is true.
        self.assertFalse(blocked)
        self.assertTrue(notified)


if __name__ == '__main__':
    unittest.main()