import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path

import secret_scanner


ORIGINAL_SECRET = "AKIAQQQQRRRRSSSSTTTT"
CHANGED_SECRET = "AKIAZZZZYYYYXXXXWWWW"


def _get(value, key):
    if isinstance(value, dict):
        return value.get(key)
    return getattr(value, key, None)


def _sha1_prefixed(secret):
    return "sha1:" + hashlib.sha1(secret.encode("utf-8")).hexdigest()


def _sha256_file(path):
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _matches_under(matches, prefix):
    relevant = []
    for match in matches:
        file_value = _get(match, "file")
        if file_value and file_value.startswith(prefix):
            relevant.append(match)
    return relevant


def _write_cache_manager_stub(repo_root):
    cache_dir = repo_root / "gen" / "cache-manager"
    cache_dir.mkdir(parents=True, exist_ok=True)
    (cache_dir / "cache_manager.py").write_text(
        "class Miss:\n"
        "    pass\n"
        "\n"
        "class CacheKey:\n"
        "    def __init__(self, spec_bundle_hash=None, gate_inputs_hash=None,"
        " gate_version=None, model_pin=None):\n"
        "        self.spec_bundle_hash = spec_bundle_hash\n"
        "        self.gate_inputs_hash = gate_inputs_hash\n"
        "        self.gate_version = gate_version\n"
        "        self.model_pin = model_pin\n"
        "\n"
        "class CachedResult:\n"
        "    def __init__(self, gate_type=None, payload=None, stored_at=None):\n"
        "        self.gate_type = gate_type\n"
        "        self.payload = payload\n"
        "        self.stored_at = stored_at\n"
        "\n"
        "def get(cache_key, repo_root=None):\n"
        "    return Miss()\n"
        "\n"
        "def put(cache_key, result, repo_root=None):\n"
        "    pass\n"
    )


def _write_decision(repo_root, decision_id, allowlist_sha256):
    decisions_dir = repo_root / "specs" / "decisions"
    decisions_dir.mkdir(parents=True, exist_ok=True)
    content = (
        "---\n"
        "id: D{0}\n"
        "title: Seal allowlist fixture {0}\n"
        "status: ratified\n"
        "owners: [lselfors]\n"
        "last_ratified_commit: 0000000000000000000000000000000000000000\n"
        "allowlist_sha256: {1}\n"
        "---\n"
        "\n"
        "Seals `.secret-allowlist.json` for an AC-SECRET-015 fixture.\n"
    ).format(decision_id, allowlist_sha256)
    (decisions_dir / "D{0}.md".format(decision_id)).write_text(content)


def _reseal(repo_root, allowlist_path, decision_id):
    digest = _sha256_file(allowlist_path)
    _write_decision(repo_root, decision_id, digest)


def _build_baseline(repo_root):
    _write_cache_manager_stub(repo_root)

    verif_dir = repo_root / "verification" / "foo"
    verif_dir.mkdir(parents=True, exist_ok=True)
    (verif_dir / "test_x.py").write_text('K = "{0}"\n'.format(ORIGINAL_SECRET))

    allowlist_path = repo_root / ".secret-allowlist.json"
    allowlist = {
        "version": 1,
        "entries": [
            {
                "file": "verification/foo/test_x.py",
                "type": "AWS Access Key",
                "hashed_secret": _sha1_prefixed(ORIGINAL_SECRET),
                "reason": "planted-fixture",
            }
        ],
    }
    allowlist_path.write_text(json.dumps(allowlist, indent=2))

    _reseal(repo_root, allowlist_path, 900)
    return allowlist_path


class ACSecret015Test(unittest.TestCase):
    def _make_repo(self):
        repo_root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, repo_root, ignore_errors=True)
        _build_baseline(repo_root)
        return repo_root

    def test_changed_secret_value_is_flagged_and_entry_becomes_unused(self):
        repo_root = self._make_repo()
        test_x = repo_root / "verification" / "foo" / "test_x.py"
        test_x.write_text('K = "{0}"\n'.format(CHANGED_SECRET))

        result = secret_scanner.scan(repo_root)

        self.assertTrue(_get(result, "flagged"))

        matches = _get(result, "matches")
        relevant = _matches_under(matches, "verification/")
        self.assertEqual(len(relevant), 1)
        self.assertEqual(_get(relevant[0], "file"), "verification/foo/test_x.py")
        self.assertEqual(_get(relevant[0], "line"), 1)

        allowed = _get(result, "allowed")
        self.assertEqual(allowed, [])

        unused = _get(result, "unused_allowlist_entries")
        self.assertEqual(len(unused), 1)
        self.assertEqual(_get(unused[0], "file"), "verification/foo/test_x.py")
        self.assertEqual(_get(unused[0], "type"), "AWS Access Key")

    def test_same_secret_in_new_file_is_flagged_while_original_stays_allowed(self):
        repo_root = self._make_repo()
        other = repo_root / "verification" / "foo" / "other.py"
        other.write_text('OTHER = "{0}"\n'.format(ORIGINAL_SECRET))

        result = secret_scanner.scan(repo_root)

        matches = _get(result, "matches")
        relevant = _matches_under(matches, "verification/")
        self.assertEqual(len(relevant), 1)
        self.assertEqual(_get(relevant[0], "file"), "verification/foo/other.py")
        self.assertEqual(_get(relevant[0], "rule_id"), "AWS Access Key")

        allowed = _get(result, "allowed")
        self.assertEqual(len(allowed), 1)
        self.assertEqual(_get(allowed[0], "file"), "verification/foo/test_x.py")

    def test_new_unlisted_line_is_flagged_alone(self):
        repo_root = self._make_repo()
        test_x = repo_root / "verification" / "foo" / "test_x.py"
        with test_x.open("a") as handle:
            handle.write('J = "{0}"\n'.format(CHANGED_SECRET))

        result = secret_scanner.scan(repo_root)

        matches = _get(result, "matches")
        relevant = _matches_under(matches, "verification/")
        self.assertEqual(len(relevant), 1)
        self.assertEqual(_get(relevant[0], "file"), "verification/foo/test_x.py")
        self.assertEqual(_get(relevant[0], "line"), 2)

    def test_entry_type_change_lets_original_finding_through(self):
        repo_root = self._make_repo()
        allowlist_path = repo_root / ".secret-allowlist.json"
        allowlist = json.loads(allowlist_path.read_text())
        allowlist["entries"][0]["type"] = "Hex High Entropy String"
        allowlist_path.write_text(json.dumps(allowlist, indent=2))
        _reseal(repo_root, allowlist_path, 901)

        result = secret_scanner.scan(repo_root)

        self.assertTrue(_get(result, "flagged"))

        matches = _get(result, "matches")
        found = False
        for match in matches:
            if (
                _get(match, "file") == "verification/foo/test_x.py"
                and _get(match, "line") == 1
                and _get(match, "rule_id") == "AWS Access Key"
            ):
                found = True
                break
        self.assertTrue(found)


if __name__ == "__main__":
    unittest.main()