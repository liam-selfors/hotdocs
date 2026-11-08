import hashlib
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import secret_scanner


def _get(value, key, default=None):
    if isinstance(value, dict):
        return value.get(key, default)
    return getattr(value, key, default)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _sha1_hash(secret: str) -> str:
    return "sha1:" + hashlib.sha1(secret.encode("utf-8")).hexdigest()


FAKE_CACHE_MANAGER_SOURCE = """
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
"""


def _write_fake_cache_manager(repo_root: Path) -> None:
    _write(repo_root / "gen" / "cache-manager" / "cache_manager.py", FAKE_CACHE_MANAGER_SOURCE)


def _write_allowlist_and_seal(repo_root: Path, entries: list) -> None:
    allowlist_obj = {"version": 1, "entries": entries}
    allowlist_bytes = json.dumps(allowlist_obj, indent=2).encode("utf-8")
    allowlist_path = repo_root / ".secret-allowlist.json"
    allowlist_path.parent.mkdir(parents=True, exist_ok=True)
    allowlist_path.write_bytes(allowlist_bytes)

    digest = hashlib.sha256(allowlist_bytes).hexdigest()
    decision = (
        "---\n"
        "id: D1\n"
        "title: Seal secret allowlist\n"
        "status: ratified\n"
        "owners: [spec-owner]\n"
        "last_ratified_commit: 0000000000000000000000000000000000000000\n"
        "allowlist_sha256: sha256:" + digest + "\n"
        "---\n"
        "\n"
        "Seals the secret allowlist for AC-SECRET-014.\n"
    )
    _write(repo_root / "specs" / "decisions" / "D1.md", decision)


class AcSecret014Test(unittest.TestCase):
    def setUp(self):
        self._tmp_dirs = []
        # Constructed from pieces so this file's own raw text never contains
        # a contiguous secret-shaped literal (this file is itself scanned).
        self.aws_secret = "AKIA" + "ABCDEFGHIJKLMNOP"
        self.hex_secret = "4b825dc642cb6eb9a060" + "e54bf8d69288fbee4904"

    def tearDown(self):
        for d in self._tmp_dirs:
            shutil.rmtree(d, ignore_errors=True)

    def _make_repo(self) -> Path:
        d = tempfile.mkdtemp()
        self._tmp_dirs.append(d)
        return Path(d)

    def test_scenario_1_planted_fixture_suppressed_and_no_notification(self):
        repo_root = self._make_repo()
        _write_fake_cache_manager(repo_root)
        _write(
            repo_root / "verification" / "foo" / "test_x.py",
            'K = "' + self.aws_secret + '"\n',
        )
        entries = [
            {
                "file": "verification/foo/test_x.py",
                "type": "AWS Access Key",
                "hashed_secret": _sha1_hash(self.aws_secret),
                "reason": "planted-fixture",
            }
        ]
        _write_allowlist_and_seal(repo_root, entries)

        recorder_calls = []

        def fake_urlopen(*args, **kwargs):
            recorder_calls.append((args, kwargs))
            return None

        with patch.dict(
            os.environ, {"VAR_COMPLIANCE_WEBHOOK_URL": "https://example.invalid/webhook"}
        ):
            with patch("urllib.request.urlopen", fake_urlopen):
                result = secret_scanner.scan(repo_root)

        flagged = _get(result, "flagged")
        matches = _get(result, "matches")
        allowed = _get(result, "allowed")
        notified = _get(result, "notified")

        self.assertFalse(flagged)
        self.assertEqual(matches, [])
        self.assertEqual(len(allowed), 1)
        entry = allowed[0]
        self.assertEqual(_get(entry, "rule_id"), "AWS Access Key")
        self.assertEqual(_get(entry, "file"), "verification/foo/test_x.py")
        self.assertEqual(_get(entry, "line"), 1)
        self.assertFalse(notified)
        self.assertEqual(recorder_calls, [])

    def test_scenario_2_public_constant_suppressed(self):
        repo_root = self._make_repo()
        _write_fake_cache_manager(repo_root)
        _write(
            repo_root / "gen" / "foo" / "g.py",
            'EMPTY = "' + self.hex_secret + '"\n',
        )
        entries = [
            {
                "file": "gen/foo/g.py",
                "type": "Hex High Entropy String",
                "hashed_secret": _sha1_hash(self.hex_secret),
                "reason": "public-constant",
            }
        ]
        _write_allowlist_and_seal(repo_root, entries)

        result = secret_scanner.scan(repo_root)

        flagged = _get(result, "flagged")
        allowed = _get(result, "allowed")

        self.assertFalse(flagged)
        self.assertEqual(len(allowed), 1)
        entry = allowed[0]
        self.assertEqual(_get(entry, "rule_id"), "Hex High Entropy String")
        self.assertEqual(_get(entry, "file"), "gen/foo/g.py")

    def test_scenario_3_unused_entry_does_not_block(self):
        repo_root = self._make_repo()
        _write_fake_cache_manager(repo_root)
        entries = [
            {
                "file": "verification/foo/old.py",
                "type": "Hex High Entropy String",
                "hashed_secret": _sha1_hash("some-value-that-matches-nothing"),
                "reason": "public-constant",
            }
        ]
        _write_allowlist_and_seal(repo_root, entries)

        result = secret_scanner.scan(repo_root)

        flagged = _get(result, "flagged")
        allowed = _get(result, "allowed")
        unused = _get(result, "unused_allowlist_entries")

        self.assertFalse(flagged)
        self.assertEqual(allowed, [])
        self.assertEqual(len(unused), 1)
        unused_entry = unused[0]
        self.assertEqual(_get(unused_entry, "file"), "verification/foo/old.py")
        self.assertEqual(_get(unused_entry, "type"), "Hex High Entropy String")

    def test_scenario_4_scan_files_repo_root_affects_suppression(self):
        repo_root = self._make_repo()
        _write_fake_cache_manager(repo_root)
        file_path = repo_root / "verification" / "foo" / "test_x.py"
        _write(file_path, 'K = "' + self.aws_secret + '"\n')
        entries = [
            {
                "file": "verification/foo/test_x.py",
                "type": "AWS Access Key",
                "hashed_secret": _sha1_hash(self.aws_secret),
                "reason": "planted-fixture",
            }
        ]
        _write_allowlist_and_seal(repo_root, entries)

        with_root = secret_scanner.scan_files([file_path], repo_root=repo_root)
        without_root = secret_scanner.scan_files([file_path])

        self.assertFalse(_get(with_root, "flagged"))
        self.assertTrue(_get(without_root, "flagged"))


if __name__ == "__main__":
    unittest.main()