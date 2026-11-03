import json
import os
import shutil
import tempfile
from pathlib import Path

import provenance_checker


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def test_llm_judge_criterion_with_trust_var_true_is_hit():
    repo_root = Path(tempfile.mkdtemp())
    try:
        spec_bundle_hash = "sha256:" + "a1" * 32

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
                    "id": "AC-FOO-002",
                    "covers": "R-FOO-002",
                    "kind": "llm-judge",
                    "result": "pass",
                    "rationale": "looks good",
                }
            ],
            "requirement_results": {"R-FOO-002": "pass"},
            "interface_drift": False,
            "mutation_score": 0.92,
            "overall": "pass",
        }

        license_scan = {
            "component_id": "comp-foo",
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

        secret_scan = {
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

        manifest = {
            "spec_bundle_hash": spec_bundle_hash,
            "model_pin": "claude-sonnet-5",
            "prompt_version": "v1",
            "retry_feedback": None,
            "pipeline_version": "v1",
            "gate_versions": gate_versions,
            "provenance_hit": False,
            "generated_at": "2026-01-01T00:00:00Z",
            "verification_run_id": "run-123",
            "verification_report": verification_report,
            "license_scan": license_scan,
            "secret_scan": secret_scan,
        }

        gen_dir = repo_root / "gen" / "foo"
        gen_dir.mkdir(parents=True)
        (gen_dir / ".provenance.json").write_text(json.dumps(manifest))

        os.environ["VAR_TRUST_JUDGE_PROVENANCE"] = "true"
        try:
            result = provenance_checker.check_provenance(
                "comp-foo", spec_bundle_hash, gate_versions, repo_root
            )
        finally:
            os.environ.pop("VAR_TRUST_JUDGE_PROVENANCE", None)

        assert _get(result, "hit") is True
    finally:
        shutil.rmtree(repo_root, ignore_errors=True)