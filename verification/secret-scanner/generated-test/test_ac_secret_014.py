import hashlib
import json
import tempfile
from pathlib import Path
from unittest import mock
import unittest

import secret_scanner


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_allowlist(repo_root: Path, entries: list) -> None:
    allowlist_path = repo_root / ".secret-allowlist.json"
    allowlist_path.write_text(
        json.dumps({"version": 1, "entries": entries}, indent=2),
        encoding="utf-8",
    )
    digest = hashlib.sha256(allowlist_path.read_bytes()).hexdigest()
    decisions_dir = repo_root / "specs" / "decisions"
    decisions_dir.mkdir(parents=True, exist_ok=True)
    (decisions_dir / "D1.md").write_text(
        "---\n"
        "id: D1\n"
        "title: Seal secret allowlist for AC-SECRET-014\n"
        "status: ratified\n"
        "owners: [lselfors@gmail.com]\n"
        "last_ratified_commit: 0000000000000000000000000000000000000000\n"
        f"allowlist_sha256: sha256:{digest}\n"
        "---\n"
        "\n"
        "Seals the secret allowlist used by this fixture.\n",
        encoding="utf-8",
    )


def _hashed(secret: str) -> str:
    return "sha1:" + hashlib.sha1(secret.encode("utf-8")).hexdigest()


class TestACSecret014(unittest.TestCase):
    def test_allowlisted_planted_fixture_suppressed_no_notification(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            secret = "AKIAABCDEFGHIJKLMNOP"
            file_rel = "verification/foo/test_x.py"
            _write(repo_root / file_rel, f'K = "{secret}"\n')
            _write_allowlist(
                repo_root,
                [
                    {
                        "file": file_rel,
                        "type": "AWS Access Key",
                        "hashed_secret": _hashed(secret),
                        "reason": "planted-fixture",
                    }
                ],
            )

            with mock.patch.dict(
                "os.environ",
                {"VAR_COMPLIANCE_WEBHOOK_URL": "https://compliance.example.invalid/hook"},
            ):
                with mock.patch("urllib.request.urlopen") as urlopen_mock:
                    result = secret_scanner.scan(repo_root)

            self.assertFalse(_get(result, "flagged"))
            self.assertEqual(_get(result, "matches"), [])
            allowed = _get(result, "allowed")
            self.assertEqual(len(allowed), 1)
            self.assertEqual(_get(allowed[0], "rule_id"), "AWS Access Key")
            self.assertEqual(_get(allowed[0], "file"), file_rel)
            self.assertEqual(_get(allowed[0], "line"), 1)
            self.assertFalse(_get(result, "notified"))
            self.assertEqual(urlopen_mock.call_count, 0)

    def test_allowlisted_public_constant_hex_suppressed(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            secret = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"
            file_rel = "gen/foo/g.py"
            _write(repo_root / file_rel, f'EMPTY = "{secret}"\n')
            _write_allowlist(
                repo_root,
                [
                    {
                        "file": file_rel,
                        "type": "Hex High Entropy String",
                        "hashed_secret": _hashed(secret),
                        "reason": "public-constant",
                    }
                ],
            )

            result = secret_scanner.scan(repo_root)

            self.assertFalse(_get(result, "flagged"))
            allowed = _get(result, "allowed")
            self.assertEqual(len(allowed), 1)
            self.assertEqual(_get(allowed[0], "rule_id"), "Hex High Entropy String")
            self.assertEqual(_get(allowed[0], "file"), file_rel)

    def test_valid_entry_matching_nothing_is_unused_and_non_blocking(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            file_rel = "verification/foo/baz.py"
            _write(repo_root / file_rel, "VALUE = 'nothing-secret-here'\n")
            fake_secret = "AKIAZZZZZZZZZZZZZZZZ"
            _write_allowlist(
                repo_root,
                [
                    {
                        "file": file_rel,
                        "type": "AWS Access Key",
                        "hashed_secret": _hashed(fake_secret),
                        "reason": "planted-fixture",
                    }
                ],
            )

            result = secret_scanner.scan(repo_root)

            self.assertFalse(_get(result, "flagged"))
            self.assertEqual(_get(result, "allowed"), [])
            unused = _get(result, "unused_allowlist_entries")
            self.assertEqual(len(unused), 1)
            self.assertEqual(_get(unused[0], "file"), file_rel)
            self.assertEqual(_get(unused[0], "type"), "AWS Access Key")

    def test_scan_files_without_repo_root_reports_path_as_given(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            secret = "AKIAABCDEFGHIJKLMNOP"
            file_rel = "verification/foo/test_x.py"
            file_path = repo_root / file_rel
            _write(file_path, f'K = "{secret}"\n')
            _write_allowlist(
                repo_root,
                [
                    {
                        "file": file_rel,
                        "type": "AWS Access Key",
                        "hashed_secret": _hashed(secret),
                        "reason": "planted-fixture",
                    }
                ],
            )

            with_root = secret_scanner.scan_files([file_path], repo_root=repo_root)
            without_root = secret_scanner.scan_files([file_path])

            self.assertFalse(_get(with_root, "flagged"))
            self.assertTrue(_get(without_root, "flagged"))


if __name__ == "__main__":
    unittest.main()