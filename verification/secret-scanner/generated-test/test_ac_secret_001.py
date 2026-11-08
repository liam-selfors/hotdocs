import tempfile
import unittest
from pathlib import Path

import secret_scanner


AWS_KEY = "AKIAABCDEFGHIJKLMNOP"

CACHE_MANAGER_STUB = '''
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


class Miss:
    pass


def get(cache_key, *, repo_root=None):
    return Miss()


def put(cache_key, result, *, repo_root=None):
    pass
'''


def _field(obj, name):
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


def _write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _write_bytes(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def _install_cache_manager_stub(repo_root):
    cm_dir = repo_root / "gen" / "cache-manager"
    cm_dir.mkdir(parents=True, exist_ok=True)
    (cm_dir / "cache_manager.py").write_text(CACHE_MANAGER_STUB)


class TestAcSecret001(unittest.TestCase):
    def test_single_match_in_gen_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            _install_cache_manager_stub(repo_root)
            _write(repo_root / "gen" / "foo" / "config.py", 'K = "%s"\n' % AWS_KEY)

            result = secret_scanner.scan(repo_root)

            matches = _field(result, "matches")
            flagged = _field(result, "flagged")

            self.assertEqual(len(matches), 1)
            match = matches[0]
            self.assertEqual(_field(match, "rule_id"), "AWS Access Key")
            self.assertEqual(_field(match, "risk_tier"), "high")
            self.assertEqual(_field(match, "file"), "gen/foo/config.py")
            self.assertEqual(_field(match, "line"), 1)
            self.assertTrue(flagged)

    def test_match_found_in_every_scanned_location(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            _install_cache_manager_stub(repo_root)

            relative_paths = [
                "README.md",
                "notes/n.md",
                "pipeline/p.py",
                "tools/t.py",
                "verification/secret-scanner/generated-test/test_x.py",
            ]
            for rel in relative_paths:
                _write(repo_root / rel, 'K = "%s"\n' % AWS_KEY)

            result = secret_scanner.scan(repo_root)
            matches = _field(result, "matches")

            matched_files = {_field(m, "file") for m in matches}
            for rel in relative_paths:
                self.assertIn(rel, matched_files)

    def test_excluded_dirs_and_non_utf8_are_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            _install_cache_manager_stub(repo_root)

            text_locations = [
                "gen/foo/__pycache__/x.txt",
                ".git/config",
                ".venv/lib/x.py",
                ".hotdocs/x.json",
                ".pytest_cache/x.txt",
                "node_modules/x.js",
            ]
            for rel in text_locations:
                _write(repo_root / rel, 'K = "%s"\n' % AWS_KEY)

            _write_bytes(
                repo_root / "gen" / "foo" / "blob.bin",
                AWS_KEY.encode("ascii") + b"\xff\xfe\xfd",
            )

            result = secret_scanner.scan(repo_root)

            self.assertFalse(_field(result, "flagged"))
            self.assertEqual(_field(result, "matches"), [])

    def test_non_secret_lines_are_not_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            _install_cache_manager_stub(repo_root)

            content = (
                "gate_version=GATE_VERSION\n"
                '{"secret_scanner": "secret_scanner@0.0.0"}\n'
                "see verification/spec-linter/BOOTSTRAP.md --retry-feedback=R-TRACK-009\n"
            )
            _write(repo_root / "gen" / "foo" / "ok.py", content)

            result = secret_scanner.scan(repo_root)

            self.assertFalse(_field(result, "flagged"))
            self.assertEqual(_field(result, "matches"), [])


if __name__ == "__main__":
    unittest.main()