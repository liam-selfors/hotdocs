import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

import license_scanner


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _write_corpus(path, corpus_version, entries, block_threshold=0.7):
    data = {
        "corpus_version": corpus_version,
        "block_threshold": block_threshold,
        "entries": entries,
    }
    with open(path, "w") as f:
        json.dump(data, f)


def _write_component(repo_root, slug="foo"):
    comp_dir = os.path.join(repo_root, "gen", slug)
    os.makedirs(comp_dir, exist_ok=True)
    with open(os.path.join(comp_dir, "sample.py"), "w") as f:
        f.write(
            "def hello():\n"
            "    return 'hello world, this is sample code for scanning'\n"
        )
    return "comp-" + slug


ENTRY_1 = {
    "reference_id": "ref-1",
    "license_family": "MIT",
    "risk_tier": "low",
    "hashes": ["hash-aaa", "hash-bbb"],
}
ENTRY_2 = {
    "reference_id": "ref-2",
    "license_family": "Apache-2.0",
    "risk_tier": "medium",
    "hashes": ["hash-ccc"],
}


class TestGateVersionAcLicense010(unittest.TestCase):
    def setUp(self):
        self.repo_root = tempfile.mkdtemp(prefix="license_scanner_test_")
        self._env_backup = os.environ.get("VAR_LICENSE_CORPUS_PATH")
        os.environ.pop("VAR_LICENSE_CORPUS_PATH", None)

    def tearDown(self):
        shutil.rmtree(self.repo_root, ignore_errors=True)
        if self._env_backup is None:
            os.environ.pop("VAR_LICENSE_CORPUS_PATH", None)
        else:
            os.environ["VAR_LICENSE_CORPUS_PATH"] = self._env_backup

    def test_gate_version_matches_scan_with_usable_corpus(self):
        component_id = _write_component(self.repo_root)
        corpus_path = os.path.join(self.repo_root, "corpus.json")
        _write_corpus(corpus_path, 4, [ENTRY_1])
        os.environ["VAR_LICENSE_CORPUS_PATH"] = corpus_path

        gv = license_scanner.gate_version(Path(self.repo_root))
        scan_result = license_scanner.scan(component_id, Path(self.repo_root))

        self.assertEqual(gv, _get(scan_result, "gate_version"))

    def test_gate_version_changes_on_corpus_version_bump_and_on_entry_add(self):
        corpus_path = os.path.join(self.repo_root, "corpus.json")
        _write_corpus(corpus_path, 4, [ENTRY_1])
        os.environ["VAR_LICENSE_CORPUS_PATH"] = corpus_path
        baseline = license_scanner.gate_version(Path(self.repo_root))

        _write_corpus(corpus_path, 5, [ENTRY_1])
        gv_version_bumped = license_scanner.gate_version(Path(self.repo_root))
        self.assertNotEqual(gv_version_bumped, baseline)

        _write_corpus(corpus_path, 4, [ENTRY_1, ENTRY_2])
        gv_entry_added = license_scanner.gate_version(Path(self.repo_root))
        self.assertNotEqual(gv_entry_added, baseline)

    def test_gate_version_matches_scan_across_unusable_corpus_states(self):
        component_id = _write_component(self.repo_root)

        os.environ.pop("VAR_LICENSE_CORPUS_PATH", None)
        gv_unset = license_scanner.gate_version(Path(self.repo_root))
        scan_unset = license_scanner.scan(component_id, Path(self.repo_root))
        self.assertEqual(gv_unset, _get(scan_unset, "gate_version"))
        self.assertEqual(gv_unset, "license_scanner@4.0.0-no-reference-corpus")

        missing_path = os.path.join(self.repo_root, "does_not_exist.json")
        os.environ["VAR_LICENSE_CORPUS_PATH"] = missing_path
        gv_missing = license_scanner.gate_version(Path(self.repo_root))
        scan_missing = license_scanner.scan(component_id, Path(self.repo_root))
        self.assertEqual(gv_missing, _get(scan_missing, "gate_version"))
        self.assertEqual(gv_missing, "license_scanner@4.0.0-corpus-unreadable")

        invalid_path = os.path.join(self.repo_root, "invalid_corpus.json")
        with open(invalid_path, "w") as f:
            json.dump(
                {
                    "corpus_version": 1,
                    "entries": [
                        {
                            "reference_id": "ref-1",
                            "license_family": "MIT",
                            "risk_tier": "bogus-tier",
                            "hashes": ["h1"],
                        }
                    ],
                },
                f,
            )
        os.environ["VAR_LICENSE_CORPUS_PATH"] = invalid_path
        gv_invalid = license_scanner.gate_version(Path(self.repo_root))
        scan_invalid = license_scanner.scan(component_id, Path(self.repo_root))
        self.assertEqual(gv_invalid, _get(scan_invalid, "gate_version"))
        self.assertEqual(gv_invalid, "license_scanner@4.0.0-corpus-invalid")

        self.assertNotEqual(gv_unset, gv_missing)
        self.assertNotEqual(gv_unset, gv_invalid)
        self.assertNotEqual(gv_missing, gv_invalid)

    def test_gate_version_never_touches_cache_manager_or_gen(self):
        repo_root = tempfile.mkdtemp(prefix="license_scanner_test_nogen_")
        try:
            cache_dir = os.path.join(repo_root, "gen", "cache-manager")
            os.makedirs(cache_dir)
            call_log = os.path.join(repo_root, "cache_manager_calls.log")

            fake_src = (
                "import dataclasses\n"
                "\n"
                "CALL_LOG = " + repr(call_log) + "\n"
                "\n"
                "def _record(name):\n"
                "    with open(CALL_LOG, 'a') as f:\n"
                "        f.write(name + chr(10))\n"
                "\n"
                "@dataclasses.dataclass\n"
                "class CacheKey:\n"
                "    spec_bundle_hash: str\n"
                "    gate_inputs_hash: str\n"
                "    gate_version: str\n"
                "    model_pin: str\n"
                "\n"
                "@dataclasses.dataclass\n"
                "class CachedResult:\n"
                "    gate_type: str\n"
                "    payload: object\n"
                "    stored_at: str\n"
                "\n"
                "class Miss:\n"
                "    pass\n"
                "\n"
                "def get(cache_key, *, repo_root=None):\n"
                "    _record('get')\n"
                "    return Miss()\n"
                "\n"
                "def put(cache_key, result, *, repo_root=None):\n"
                "    _record('put')\n"
            )
            with open(os.path.join(cache_dir, "cache_manager.py"), "w") as f:
                f.write(fake_src)

            os.environ.pop("VAR_LICENSE_CORPUS_PATH", None)

            gv = license_scanner.gate_version(Path(repo_root))

            self.assertIsInstance(gv, str)
            self.assertGreater(len(gv), 0)
            self.assertFalse(
                os.path.exists(call_log),
                "gate_version must never call cache-manager's get/put",
            )
        finally:
            shutil.rmtree(repo_root, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()