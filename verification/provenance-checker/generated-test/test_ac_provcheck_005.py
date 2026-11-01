import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

import provenance_checker


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


class TestACProvcheck005(unittest.TestCase):
    """AC-PROVCHECK-005 / R-PROVCHECK-002."""

    def setUp(self):
        self._tmpdir = tempfile.mkdtemp()
        self.repo_root = Path(self._tmpdir)
        self._old_env = os.environ.get("VAR_TRUST_JUDGE_PROVENANCE")
        os.environ["VAR_TRUST_JUDGE_PROVENANCE"] = "true"

    def tearDown(self):
        shutil.rmtree(self._tmpdir, ignore_errors=True)
        if self._old_env is None:
            os.environ.pop("VAR_TRUST_JUDGE_PROVENANCE", None)
        else:
            os.environ["VAR_TRUST_JUDGE_PROVENANCE"] = self._old_env

    def test_hash_match_with_llm_judge_criterion_and_trust_var_true_is_hit(self):
        spec_bundle_hash = "sha256:" + "a" * 64

        gate_versions = {
            "compiler": "criterion-compiler@1.0.0",
            "generated_test": "generated_test@1.0.0",
            "verifier": "verifier-orchestrator@2.0.0",
            "license_scanner": "license_scanner@3.1.0",
            "secret_scanner": "secret_scanner@0.0.0",
        }

        verification_report = {
            "component_id": "comp-foo",
            "criteria": [
                {
                    "id": "AC-FOO-001",
                    "covers": "R-FOO-001",
                    "kind": "compiled",
                    "result": "pass",
                },
                {
                    "id": "AC-FOO-002",
                    "covers": "R-FOO-002",
                    "kind": "llm-judge",
                    "result": "pass",
                    "rationale": "looks fine",
                },
            ],
            "requirement_results": {"R-FOO-001": "pass", "R-FOO-002": "pass"},
            "interface_drift": False,
            "mutation_score": 1.0,
            "overall": "pass",
        }

        license_scan = {
            "component_id": "comp-foo",
            "gate_version": "license_scanner@3.1.0",
            "similarity_score": 0.0,
            "block_threshold": 0.70,
            "blocked": False,
            "matches": [],
            "notified": False,
            "notification_delivery_error": None,
            "cache_hit": False,
        }

        secret_scan = {
            "scope": "full",
            "gate_version": "secret_scanner@0.0.0",
            "flagged": False,
            "matches": [],
            "notified": False,
            "notification_delivery_error": None,
            "cache_hit": False,
        }

        manifest = {
            "spec_bundle_hash": spec_bundle_hash,
            "gate_versions": gate_versions,
            "verification_report": verification_report,
            "license_scan": license_scan,
            "secret_scan": secret_scan,
        }

        foo_dir = self.repo_root / "gen" / "foo"
        foo_dir.mkdir(parents=True)
        (foo_dir / ".provenance.json").write_text(
            json.dumps(manifest), encoding="utf-8"
        )

        result = provenance_checker.check_provenance(
            "comp-foo",
            spec_bundle_hash,
            gate_versions,
            self.repo_root,
        )

        self.assertTrue(_get(result, "hit"))
        self.assertEqual(_get(result, "verification_report"), verification_report)
        self.assertEqual(_get(result, "license_scan"), license_scan)
        self.assertEqual(_get(result, "secret_scan"), secret_scan)


if __name__ == "__main__":
    unittest.main()