import json
import tempfile
import unittest
from pathlib import Path

import provenance_writer


EXPECTED_TOP_LEVEL_KEYS = {
    "spec_bundle_hash",
    "model_pin",
    "prompt_version",
    "retry_feedback",
    "pipeline_version",
    "gate_versions",
    "provenance_hit",
    "generated_at",
    "verification_run_id",
    "verification_report",
    "license_scan",
    "secret_scan",
}


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


class TestProvenanceManifestTopLevelKeys(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo_root = Path(self._tmp.name)
        self.component_id = "comp-foo"
        self.slug = "foo"

        # Pre-create the directories a real pipeline run would already have
        # produced (generator output dir, verification output dir).
        (self.repo_root / "gen" / self.slug).mkdir(parents=True, exist_ok=True)
        (self.repo_root / "verification" / self.slug).mkdir(
            parents=True, exist_ok=True
        )

    def tearDown(self):
        self._tmp.cleanup()

    def _build_inputs(self):
        generation_result = {
            "component_id": self.component_id,
            "spec_bundle_hash": "sha256:" + "0" * 64,
            "model": "claude-sonnet-5",
            "prompt_version": "v1",
            "cache_hit": False,
            "files": {"foo.py": "print('hi')\n"},
            "model_call_error": None,
            "refused": None,
            "retry_feedback": None,
        }

        verification_report = {
            "component_id": self.component_id,
            "criteria": [
                {
                    "id": "AC-FOO-001",
                    "covers": "R-FOO-001",
                    "kind": "compiled",
                    "result": "pass",
                }
            ],
            "requirement_results": {"R-FOO-001": "pass"},
            "interface_drift": False,
            "mutation_score": 0.92,
            "overall": "pass",
        }

        license_scan_result = {
            "component_id": self.component_id,
            "gate_version": "license_scanner@4.0.3",
            "evaluated": True,
            "reason": None,
            "similarity_score": 0.1,
            "block_threshold": 0.70,
            "blocked": False,
            "matches": [],
            "notified": False,
            "notification_delivery_error": None,
            "cache_hit": False,
        }

        secret_scan_result = {
            "scope": "full",
            "gate_version": "secret_scanner@3.0.0+detect-secrets.1.5.0",
            "flagged": False,
            "matches": [],
            "allowed": [],
            "unused_allowlist_entries": [],
            "notified": False,
            "notification_delivery_error": None,
            "cache_hit": False,
        }

        gate_versions = {
            "compiler": "1.0.0",
            "license_scanner": "license_scanner@4.0.3",
            "secret_scanner": "secret_scanner@3.0.0+detect-secrets.1.5.0",
        }

        return provenance_writer.ProvenanceInputs(
            component_id=self.component_id,
            generation_result=generation_result,
            verification_report=verification_report,
            license_scan_result=license_scan_result,
            secret_scan_result=secret_scan_result,
            provenance_hit=False,
            attempts=1,
            gate_versions=gate_versions,
        )

    def test_manifest_top_level_keys_exactly_match_spec(self):
        inputs = self._build_inputs()

        provenance_writer.write_provenance(
            self.component_id, inputs, self.repo_root
        )

        gen_manifest_path = (
            self.repo_root / "gen" / self.slug / ".provenance.json"
        )
        verification_manifest_path = (
            self.repo_root / "verification" / self.slug / ".provenance.json"
        )

        for manifest_path in (gen_manifest_path, verification_manifest_path):
            self.assertTrue(
                manifest_path.is_file(),
                f"expected manifest to be written at {manifest_path}",
            )
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)

            self.assertIsInstance(manifest, dict)
            self.assertEqual(
                set(manifest.keys()),
                EXPECTED_TOP_LEVEL_KEYS,
                f"manifest at {manifest_path} has keys "
                f"{sorted(manifest.keys())}, expected exactly "
                f"{sorted(EXPECTED_TOP_LEVEL_KEYS)}",
            )


if __name__ == "__main__":
    unittest.main()