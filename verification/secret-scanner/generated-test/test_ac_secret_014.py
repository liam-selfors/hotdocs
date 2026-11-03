import hashlib
import json
import os
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


def _hash(secret):
    return "sha1:" + hashlib.sha1(secret.encode("utf-8")).hexdigest()


def _write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_allowlist(repo_root, entries):
    _write(
        repo_root / ".secret-allowlist.json",
        json.dumps({"version": 1, "entries": entries}),
    )


class _RecordingUrlopen:
    def __init__(self):
        self.calls = []

    def __call__(self, *args, **kwargs):
        self.calls.append((args, kwargs))


class TestAcSecret014(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self.repo_root = Path(self._tmp)
        self._env_backup = dict(os.environ)
        self._orig_urlopen = urllib.request.urlopen

    def tearDown(self):
        urllib.request.urlopen = self._orig_urlopen
        os.environ.clear()
        os.environ.update(self._env_backup)
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_suppressed_finding_not_notified_recorder_unused(self):
        secret = "AKIAABCDEFGHIJKLMNOP"
        rel_file = "verification/foo/test_x.py"
        _write(self.repo_root / rel_file, 'K = "%s"\n' % secret)
        _write_allowlist(
            self.repo_root,
            [
                {
                    "file": rel_file,
                    "type": "AWS Access Key",
                    "hashed_secret": _hash(secret),
                    "reason": "planted-fixture",
                }
            ],
        )
        os.environ["VAR_COMPLIANCE_WEBHOOK_URL"] = "https://compliance.example.invalid/hook"

        recorder = _RecordingUrlopen()
        urllib.request.urlopen = recorder

        result = secret_scanner.scan(self.repo_root)

        self.assertFalse(_get(result, "flagged"))
        self.assertEqual(_get(result, "matches"), [])

        allowed = _get(result, "allowed")
        self.assertEqual(len(allowed), 1)
        entry = allowed[0]
        self.assertEqual(_get(entry, "rule_id"), "AWS Access Key")
        self.assertEqual(_get(entry, "file"), rel_file)
        self.assertEqual(_get(entry, "line"), 1)

        self.assertFalse(_get(result, "notified"))
        self.assertEqual(recorder.calls, [])

    def test_hex_high_entropy_public_constant_allowed(self):
        secret = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"
        rel_file = "gen/foo/g.py"
        _write(self.repo_root / rel_file, 'EMPTY = "%s"\n' % secret)
        _write_allowlist(
            self.repo_root,
            [
                {
                    "file": rel_file,
                    "type": "Hex High Entropy String",
                    "hashed_secret": _hash(secret),
                    "reason": "public-constant",
                }
            ],
        )

        result = secret_scanner.scan(self.repo_root)

        self.assertFalse(_get(result, "flagged"))
        allowed = _get(result, "allowed")
        self.assertEqual(len(allowed), 1)
        entry = allowed[0]
        self.assertEqual(_get(entry, "rule_id"), "Hex High Entropy String")
        self.assertEqual(_get(entry, "file"), rel_file)

    def test_unused_entry_listed_and_does_not_block(self):
        secret = "AKIAABCDEFGHIJKLMNOP"
        rel_file = "verification/foo/old.py"
        _write(self.repo_root / rel_file, "# no secrets here\n")
        _write_allowlist(
            self.repo_root,
            [
                {
                    "file": rel_file,
                    "type": "AWS Access Key",
                    "hashed_secret": _hash(secret),
                    "reason": "planted-fixture",
                }
            ],
        )

        result = secret_scanner.scan(self.repo_root)

        self.assertFalse(_get(result, "flagged"))
        self.assertEqual(_get(result, "allowed"), [])

        unused = _get(result, "unused_allowlist_entries")
        self.assertEqual(len(unused), 1)
        self.assertEqual(_get(unused[0], "file"), rel_file)
        self.assertEqual(_get(unused[0], "type"), "AWS Access Key")

    def test_scan_files_repo_root_affects_suppression(self):
        secret = "AKIAABCDEFGHIJKLMNOP"
        rel_file = "verification/foo/test_x.py"
        file_path = self.repo_root / rel_file
        _write(file_path, 'K = "%s"\n' % secret)
        _write_allowlist(
            self.repo_root,
            [
                {
                    "file": rel_file,
                    "type": "AWS Access Key",
                    "hashed_secret": _hash(secret),
                    "reason": "planted-fixture",
                }
            ],
        )

        with_root = secret_scanner.scan_files([file_path], repo_root=self.repo_root)
        without_root = secret_scanner.scan_files([file_path])

        self.assertFalse(_get(with_root, "flagged"))
        self.assertTrue(_get(without_root, "flagged"))


if __name__ == "__main__":
    unittest.main()