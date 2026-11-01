import contextlib
import hashlib
import io
import json
import os
import re
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import license_scanner


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _tokenize(text):
    text = re.sub(r'/\*.*?\*/', ' ', text, flags=re.S)
    text = re.sub(r'""".*?"""', ' ', text, flags=re.S)
    text = re.sub(r"'''.*?'''", ' ', text, flags=re.S)
    text = re.sub(r'//.*', '', text)
    text = re.sub(r'#.*', '', text)
    tokens = re.findall(r'[A-Za-z_][A-Za-z0-9_]*|\d+', text)
    return [t.lower() for t in tokens]


def _window_hashes(tokens, n=9):
    hashes = []
    for i in range(len(tokens) - n + 1):
        window = tokens[i:i + n]
        joined = '\x1f'.join(window)
        hashes.append(hashlib.sha256(joined.encode('utf-8')).hexdigest())
    return hashes


class AcLicense001Test(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.repo_root = Path(self._tmp.name)
        self._env_backup = dict(os.environ)
        os.environ.pop('VAR_COMPLIANCE_WEBHOOK_URL', None)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._env_backup)
        self._tmp.cleanup()

    def _write(self, rel_path, content):
        path = self.repo_root / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        return path

    def test_similarity_at_block_threshold_blocks_merge(self):
        # Ten distinct identifier tokens -> exactly two overlapping 9-token
        # windows, so a corpus holding both windows' hashes yields a
        # similarity_score of 1.0 (>= any configured block_threshold).
        source_text = "alpha beta gamma delta epsilon zeta eta theta iota kappa\n"
        self._write('gen/widget/widget.py', source_text)

        tokens = _tokenize(source_text)
        hashes = _window_hashes(tokens, 9)
        self.assertEqual(len(hashes), 2)

        corpus = {
            "corpus_version": 1,
            "block_threshold": 0.70,
            "entries": [
                {
                    "reference_id": "ref-001",
                    "license_family": "GPL",
                    "risk_tier": "high",
                    "hashes": hashes,
                }
            ],
        }
        self._write('license-corpus.json', json.dumps(corpus))
        os.environ['VAR_LICENSE_CORPUS_PATH'] = 'license-corpus.json'

        result = license_scanner.scan('comp-widget', self.repo_root)

        similarity_score = _get(result, 'similarity_score')
        block_threshold = _get(result, 'block_threshold')
        blocked = _get(result, 'blocked')

        self.assertIsNotNone(similarity_score)
        self.assertIsNotNone(block_threshold)
        self.assertGreaterEqual(similarity_score, block_threshold)
        self.assertIs(blocked, True)

        matches = _get(result, 'matches') or []
        self.assertTrue(len(matches) > 0)
        self.assertEqual(_get(matches[0], 'reference_id'), 'ref-001')

        argv = ['comp-widget', '--repo-root=' + str(self.repo_root), '--format=json']
        stdout = io.StringIO()
        exit_code = None
        with contextlib.redirect_stdout(stdout):
            try:
                ret = license_scanner.main(argv)
            except SystemExit as exc:
                exit_code = exc.code
            else:
                exit_code = ret

        self.assertEqual(exit_code, 1)
        printed = json.loads(stdout.getvalue())
        self.assertIs(_get(printed, 'blocked'), True)


if __name__ == '__main__':
    unittest.main()