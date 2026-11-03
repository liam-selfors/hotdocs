import json
import tempfile
import unittest
from pathlib import Path

import provenance_writer


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


class TestAcProv003(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.repo_root = Path(self._tmp.name)

        self.component_id = "comp-prov-gate-sample"
        self.slug = "prov-gate-sample"

        # Reported versions as they would be surfaced by each gate itself.
        self.gate_versions = {
            "cache_manager": "cache-manager@1.2.3",
            "criterion_compiler": "criterion-compiler@1.0.0",
            "license_scanner": "license_scanner@4.0.3",
        }

        self.generation_result = {
            "component_id": self.component_id,
            "spec_bundle_hash": "sha256:" + "a" * 64,
            "model": "claude-sonnet-5",
            "prompt_version": "v1",
            "cache_hit": False,
            "files": {"spec_linter.py": "# fixture content\n"},
            "model_call_error": None,
            "refused": None,
            "retry_feedback": None,
        }

        self.verification_report = {
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
            "mutation_score": 1.0,
            "overall": "pass",
        }

        self.license_scan_result = {
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

        self.secret_scan_result = {
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

    def _build_inputs(self):
        inputs_cls = getattr(provenance_writer, "ProvenanceInputs", None)
        fields = dict(
            component_id=self.component_id,
            generation_result=self.generation_result,
            verification_report=self.verification_report,
            license_scan_result=self.license_scan_result,
            secret_scan_result=self.secret_scan_result,
            provenance_hit=False,
            attempts=1,
            gate_versions=self.gate_versions,
        )
        if inputs_cls is not None:
            return inputs_cls(**fields)
        return fields

    def test_gate_versions_contains_exactly_reported_values_unmodified(self):
        inputs = self._build_inputs()

        provenance_writer.write_provenance(
            self.component_id, inputs, self.repo_root
        )

        gen_manifest_path = (
            self.repo_root / "gen" / self.slug / ".provenance.json"
        )
        verify_manifest_path = (
            self.repo_root / "verification" / self.slug / ".provenance.json"
        )

        self.assertTrue(
            gen_manifest_path.is_file(),
            f"expected manifest at {gen_manifest_path}",
        )
        self.assertTrue(
            verify_manifest_path.is_file(),
            f"expected manifest at {verify_manifest_path}",
        )

        with open(gen_manifest_path, "r", encoding="utf-8") as f:
            gen_manifest = json.load(f)
        with open(verify_manifest_path, "r", encoding="utf-8") as f:
            verify_manifest = json.load(f)

        gen_gate_versions = _get(gen_manifest, "gate_versions")
        verify_gate_versions = _get(verify_manifest, "gate_versions")

        self.assertEqual(gen_gate_versions, self.gate_versions)
        self.assertEqual(verify_gate_versions, self.gate_versions)

        self.assertEqual(len(gen_gate_versions), 3)
        self.assertEqual(
            set(gen_gate_versions.keys()),
            {"cache_manager", "criterion_compiler", "license_scanner"},
        )
        for key, expected_value in self.gate_versions.items():
            self.assertEqual(gen_gate_versions[key], expected_value)
            self.assertEqual(verify_gate_versions[key], expected_value)


if __name__ == "__main__":
    unittest.main()