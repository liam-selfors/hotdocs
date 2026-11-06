import shutil
import tempfile
import unittest
import urllib.request
from pathlib import Path

import secret_scanner


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


_CACHE_MANAGER_SOURCE = '''
class Miss:
    payload = None


class CachedResult:
    def __init__(self, gate_type, payload, stored_at):
        self.gate_type = gate_type
        self.payload = payload
        self.stored_at = stored_at


class CacheKey:
    def __init__(self, spec_bundle_hash, gate_inputs_hash, gate_version, model_pin):
        self.spec_bundle_hash = spec_bundle_hash
        self.gate_inputs_hash = gate_inputs_hash
        self.gate_version = gate_version
        self.model_pin = model_pin


def get(cache_key, repo_root=None):
    return Miss()


def put(cache_key, cached_result, repo_root=None):
    pass
'''


def _write_fake_cache_manager(repo_root):
    cache_dir = repo_root / "gen" / "cache-manager"
    cache_dir.mkdir(parents=True, exist_ok=True)
    (cache_dir / "cache_manager.py").write_text(_CACHE_MANAGER_SOURCE, encoding="utf-8")


class _FakeHTTPResponse:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def read(self):
        return b"{}"


def _fake_urlopen(*args, **kwargs):
    return _FakeHTTPResponse()


class AcSecret001Test(unittest.TestCase):
    AWS_KEY = "AKIAABCDEFGHIJKLMNOP"

    def setUp(self):
        self._orig_urlopen = urllib.request.urlopen
        urllib.request.urlopen = _fake_urlopen

    def tearDown(self):
        urllib.request.urlopen = self._orig_urlopen

    def _make_repo_root(self):
        repo_root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, repo_root, ignore_errors=True)
        _write_fake_cache_manager(repo_root)
        return repo_root

    def test_single_match_in_gen_file(self):
        repo_root = self._make_repo_root()
        foo_dir = repo_root / "gen" / "foo"
        foo_dir.mkdir(parents=True, exist_ok=True)
        (foo_dir / "config.py").write_text(
            'K = "{}"\n'.format(self.AWS_KEY), encoding="utf-8"
        )

        result = secret_scanner.scan(repo_root)

        matches = _get(result, "matches")
        self.assertEqual(len(matches), 1)
        match = matches[0]
        self.assertIsInstance(match, dict)
        self.assertEqual(_get(match, "rule_id"), "AWS Access Key")
        self.assertEqual(_get(match, "risk_tier"), "high")
        self.assertEqual(_get(match, "file"), "gen/foo/config.py")
        self.assertEqual(_get(match, "line"), 1)
        self.assertTrue(_get(result, "flagged"))
        for key in match:
            self.assertNotIn("secret", key.lower())
            self.assertNotIn("hash", key.lower())

    def test_match_found_across_various_file_types(self):
        repo_root = self._make_repo_root()
        key_line = "{}\n".format(self.AWS_KEY)
        rel_paths = [
            "README.md",
            "notes/n.md",
            "pipeline/p.py",
            "tools/t.py",
            "verification/secret-scanner/generated-test/test_x.py",
        ]
        for rel in rel_paths:
            p = repo_root / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(key_line, encoding="utf-8")

        result = secret_scanner.scan(repo_root)

        matches = _get(result, "matches")
        matched_files = {_get(m, "file") for m in matches}
        for rel in rel_paths:
            self.assertIn(rel, matched_files)

    def test_skipped_directories_and_non_utf8_file_are_ignored(self):
        repo_root = self._make_repo_root()
        key = self.AWS_KEY

        skip_rel_paths = [
            "gen/foo/__pycache__/x.txt",
            ".git/config",
            ".venv/lib/x.py",
            ".hotdocs/x.json",
            ".pytest_cache/x.txt",
            "node_modules/x.js",
        ]
        for rel in skip_rel_paths:
            p = repo_root / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(key + "\n", encoding="utf-8")

        blob_path = repo_root / "gen" / "foo" / "blob.bin"
        blob_path.parent.mkdir(parents=True, exist_ok=True)
        blob_path.write_bytes(b"\xff\xfe" + key.encode("ascii") + b"\x80\x81")

        result = secret_scanner.scan(repo_root)

        self.assertFalse(_get(result, "flagged"))
        self.assertEqual(_get(result, "matches"), [])

    def test_benign_lines_produce_no_matches(self):
        repo_root = self._make_repo_root()
        content = (
            "gate_version=GATE_VERSION\n"
            '{"secret_scanner": "secret_scanner@0.0.0"}\n'
            "see verification/spec-linter/BOOTSTRAP.md --retry-feedback=R-TRACK-009\n"
        )
        ok_path = repo_root / "gen" / "foo" / "ok.py"
        ok_path.parent.mkdir(parents=True, exist_ok=True)
        ok_path.write_text(content, encoding="utf-8")

        result = secret_scanner.scan(repo_root)

        self.assertFalse(_get(result, "flagged"))
        self.assertEqual(_get(result, "matches"), [])


if __name__ == "__main__":
    unittest.main()