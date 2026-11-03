import json
import tempfile
import unittest
from pathlib import Path

import provenance_writer


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _make_inputs(**kwargs):
    cls = getattr(provenance_writer, "ProvenanceInputs", None)
    if cls is not None:
        return cls(**kwargs)
    return dict(kwargs)


class AcProv012Test(unittest.TestCase):
    def test_pipeline_version_identical_and_matches_constant(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)

            generation_result_a = {
                "component_id": "comp-alpha",
                "spec_bundle_hash": "sha256:" + "a" * 64,
                "model": "claude-sonnet-5",
                "prompt_version": "v1",
                "cache_hit": False,
                "files": {"alpha.py": "print('alpha')"},
                "model_call_error": None,
                "refused": None,
                "retry_feedback": None,
            }
            verification_report_a = {
                "component_id": "comp-alpha",
                "criteria": [
                    {"id": "AC-ALPHA-001", "covers": "R-ALPHA-001", "kind": "compiled", "result": "pass"},
                ],
                "requirement_results": {"R-ALPHA-001": "pass"},
                "interface_drift": False,
                "mutation_score": 1.0,
                "overall": "pass",
            }
            license_scan_a = {
                "component_id": "comp-alpha",
                "gate_version": "license_scanner@4.0.0-no-reference-corpus",
                "evaluated": False,
                "reason": "no-reference-corpus",
                "similarity_score": None,
                "block_threshold": None,
                "blocked": False,
                "matches": [],
                "notified": False,
                "notification_delivery_error": None,
                "cache_hit": False,
            }
            secret_scan_a = {
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

            inputs_a = _make_inputs(
                component_id="comp-alpha",
                generation_result=generation_result_a,
                verification_report=verification_report_a,
                license_scan_result=license_scan_a,
                secret_scan_result=secret_scan_a,
                provenance_hit=False,
                attempts=1,
                gate_versions={"compiler": "1.0.0"},
            )

            generation_result_b = {
                "component_id": "comp-beta",
                "spec_bundle_hash": "sha256:" + "b" * 64,
                "model": "claude-sonnet-5",
                "prompt_version": "v2",
                "cache_hit": True,
                "files": {},
                "model_call_error": None,
                "refused": "sealed-component",
                "retry_feedback": ["R-BETA-003"],
            }
            license_scan_b = {
                "component_id": "comp-beta",
                "gate_version": "license_scanner@4.0.3",
                "evaluated": True,
                "reason": None,
                "similarity_score": 0.2,
                "block_threshold": 0.70,
                "blocked": False,
                "matches": [],
                "notified": False,
                "notification_delivery_error": None,
                "cache_hit": True,
            }
            secret_scan_b = {
                "scope": "full",
                "gate_version": "secret_scanner@3.0.0+detect-secrets.1.5.0",
                "flagged": True,
                "matches": [
                    {"rule_id": "AWS Access Key", "risk_tier": "high", "file": "gen/beta/config.py", "line": 12}
                ],
                "allowed": [],
                "unused_allowlist_entries": [],
                "notified": True,
                "notification_delivery_error": None,
                "cache_hit": False,
            }

            inputs_b = _make_inputs(
                component_id="comp-beta",
                generation_result=generation_result_b,
                verification_report=None,
                license_scan_result=license_scan_b,
                secret_scan_result=secret_scan_b,
                provenance_hit=True,
                attempts=3,
                gate_versions={"compiler": "2.0.0", "license_scanner": "4.0.3"},
            )

            provenance_writer.write_provenance("comp-alpha", inputs_a, repo_root)
            provenance_writer.write_provenance("comp-beta", inputs_b, repo_root)

            manifest_a_gen = json.loads((repo_root / "gen" / "alpha" / ".provenance.json").read_text())
            manifest_a_ver = json.loads((repo_root / "verification" / "alpha" / ".provenance.json").read_text())
            manifest_b_gen = json.loads((repo_root / "gen" / "beta" / ".provenance.json").read_text())
            manifest_b_ver = json.loads((repo_root / "verification" / "beta" / ".provenance.json").read_text())

            pipeline_version_constant = provenance_writer.PIPELINE_VERSION

            versions = [
                _get(manifest_a_gen, "pipeline_version"),
                _get(manifest_a_ver, "pipeline_version"),
                _get(manifest_b_gen, "pipeline_version"),
                _get(manifest_b_ver, "pipeline_version"),
            ]

            for version in versions:
                self.assertEqual(version, pipeline_version_constant)

            self.assertTrue(all(v == versions[0] for v in versions))


if __name__ == "__main__":
    unittest.main()