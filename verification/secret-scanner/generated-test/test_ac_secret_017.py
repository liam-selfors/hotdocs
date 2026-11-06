import contextlib
import hashlib
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path

import secret_scanner


AWS_KEY_T = "AKIAABCDEFGHIJKLMNOP"
HEX_G = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"
AWS_KEY_C = "AKIAZZZZYYYYXXXXWWWW"


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _sha1_of(secret):
    return "sha1:" + hashlib.sha1(secret.encode()).hexdigest()


class TestACSecret017(unittest.TestCase):
    def setUp(self):
        self._tmpdirs = []

    def tearDown(self):
        for d in self._tmpdirs:
            shutil.rmtree(d, ignore_errors=True)

    def _mkrepo(self):
        d = Path(tempfile.mkdtemp(prefix="ac-secret-017-"))
        self._tmpdirs.append(d)
        return d

    def _write(self, repo_root, rel_path, content):
        p = repo_root / rel_path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
        return p

    def _build_scenario1_repo(self):
        repo_root = self._mkrepo()
        self._write(repo_root, "verification/foo/t.py", 'K = "%s"\n' % AWS_KEY_T)
        self._write(repo_root, "gen/foo/g.py", 'EMPTY = "%s"\n' % HEX_G)
        self._write(repo_root, "gen/foo/c.py", 'C = "%s"\n' % AWS_KEY_C)
        return repo_root

    def test_propose_two_entries_one_ineligible_no_write(self):
        repo_root = self._build_scenario1_repo()

        result = secret_scanner.propose(repo_root)

        allowlist = _get(result, "allowlist")
        entries = _get(allowlist, "entries")
        ineligible = _get(result, "ineligible")

        self.assertEqual(len(entries), 2)

        first = entries[0]
        self.assertEqual(_get(first, "file"), "gen/foo/g.py")
        self.assertEqual(_get(first, "type"), "Hex High Entropy String")
        self.assertEqual(_get(first, "reason"), "public-constant")
        self.assertEqual(_get(first, "hashed_secret"), _sha1_of(HEX_G))

        second = entries[1]
        self.assertEqual(_get(second, "file"), "verification/foo/t.py")
        self.assertEqual(_get(second, "type"), "AWS Access Key")
        self.assertEqual(_get(second, "reason"), "planted-fixture")
        self.assertEqual(_get(second, "hashed_secret"), _sha1_of(AWS_KEY_T))

        self.assertEqual(len(ineligible), 1)
        bad = ineligible[0]
        self.assertEqual(_get(bad, "file"), "gen/foo/c.py")
        self.assertEqual(_get(bad, "line"), 1)
        self.assertEqual(_get(bad, "rule_id"), "AWS Access Key")

        self.assertFalse((repo_root / ".secret-allowlist.json").exists())

    def test_propose_existing_sealed_entry_not_duplicated(self):
        repo_root = self._mkrepo()
        self._write(repo_root, "verification/foo/t.py", 'K = "%s"\n' % AWS_KEY_T)

        allowlist_doc = {
            "version": 1,
            "entries": [
                {
                    "file": "verification/foo/t.py",
                    "type": "AWS Access Key",
                    "hashed_secret": _sha1_of(AWS_KEY_T),
                    "reason": "planted-fixture",
                }
            ],
        }
        allowlist_content = json.dumps(allowlist_doc, indent=2)
        allowlist_path = repo_root / ".secret-allowlist.json"
        allowlist_path.write_text(allowlist_content)
        allowlist_bytes = allowlist_path.read_bytes()
        allowlist_sha256 = "sha256:" + hashlib.sha256(allowlist_bytes).hexdigest()

        decisions_dir = repo_root / "specs" / "decisions"
        decisions_dir.mkdir(parents=True, exist_ok=True)
        (decisions_dir / "D1.md").write_text(
            "---\n"
            "id: D1\n"
            "title: Seal the secret allowlist\n"
            "status: ratified\n"
            "owners: [qa-bot@example.com]\n"
            "last_ratified_commit: 0000000000000000000000000000000000000000\n"
            "allowlist_sha256: %s\n"
            "---\n\n"
            "Seals the current `.secret-allowlist.json`.\n" % allowlist_sha256
        )

        result = secret_scanner.propose(repo_root)
        allowlist = _get(result, "allowlist")
        entries = _get(allowlist, "entries")

        matching = [
            e
            for e in entries
            if _get(e, "file") == "verification/foo/t.py"
            and _get(e, "type") == "AWS Access Key"
        ]
        self.assertEqual(len(matching), 1)
        self.assertEqual(_get(matching[0], "hashed_secret"), _sha1_of(AWS_KEY_T))

    def test_propose_invalid_allowlist_raises(self):
        repo_root = self._mkrepo()
        self._write(repo_root, "verification/foo/t.py", 'K = "%s"\n' % AWS_KEY_T)

        allowlist_doc = {
            "version": 1,
            "entries": [
                {
                    "file": "verification/foo/t.py",
                    "type": "AWS Access Key",
                    "hashed_secret": _sha1_of(AWS_KEY_T),
                    "reason": "planted-fixture",
                }
            ],
        }
        (repo_root / ".secret-allowlist.json").write_text(
            json.dumps(allowlist_doc, indent=2)
        )
        # Deliberately no sealing decision anywhere under specs/decisions/:
        # this allowlist is unsealed, hence invalid.

        with self.assertRaises(secret_scanner.AllowlistInvalidError):
            secret_scanner.propose(repo_root)

    def test_cli_propose_exit_codes(self):
        repo_root = self._build_scenario1_repo()

        stdout1 = io.StringIO()
        with contextlib.redirect_stdout(stdout1):
            exit_code1 = secret_scanner.main(
                ["propose", "--repo-root=%s" % repo_root]
            )

        self.assertEqual(exit_code1, 1)
        payload1 = json.loads(stdout1.getvalue())
        self.assertIn("allowlist", payload1)
        self.assertIn("ineligible", payload1)

        (repo_root / "gen" / "foo" / "c.py").unlink()

        stdout2 = io.StringIO()
        with contextlib.redirect_stdout(stdout2):
            exit_code2 = secret_scanner.main(
                ["propose", "--repo-root=%s" % repo_root]
            )

        self.assertEqual(exit_code2, 0)


if __name__ == "__main__":
    unittest.main()