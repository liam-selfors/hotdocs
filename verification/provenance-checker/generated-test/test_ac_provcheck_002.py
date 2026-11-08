import json
import tempfile
from pathlib import Path

import provenance_checker


def test_spec_bundle_hash_mismatch_is_definitive_miss():
    with tempfile.TemporaryDirectory() as tmp:
        repo_root = Path(tmp)
        gen_dir = repo_root / "gen" / "foo"
        gen_dir.mkdir(parents=True)

        stored_hash = "sha256:" + "a" * 64
        gate_versions = {
            "compiler": "criterion-compiler@1.0.0",
            "generated_test": "generated_test@1.0.0",
            "verifier": "verifier-orchestrator@2.0.0",
            "license_scanner": "license_scanner@4.0.3+9f2c41ab07de",
            "secret_scanner": "secret_scanner@0.0.0",
        }

        manifest = {
            "spec_bundle_hash": stored_hash,
            "model_pin": "claude-sonnet-5",
            "prompt_version": "v1",
            "retry_feedback": None,
            "pipeline_version": "v1",
            "gate_versions": gate_versions,
            "provenance_hit": False,
            "generated_at": "2026-01-01T00:00:00Z",
            "verification_run_id": "run-123",
            "verification_report": {
                "component_id": "comp-foo",
                "criteria": [
                    {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"},
                ],
                "requirement_results": {"R-FOO-001": "pass"},
                "interface_drift": False,
                "mutation_score": 0.92,
                "overall": "pass",
            },
            "license_scan": {
                "component_id": "comp-foo",
                "gate_version": "license_scanner@4.0.3+9f2c41ab07de",
                "evaluated": True,
                "reason": None,
                "similarity_score": 0.1,
                "block_threshold": 0.70,
                "blocked": False,
                "matches": [],
                "notified": False,
                "notification_delivery_error": None,
                "cache_hit": False,
            },
            "secret_scan": {
                "scope": "full",
                "gate_version": "secret_scanner@3.1.0+detect-secrets.1.5.0",
                "flagged": False,
                "matches": [],
                "allowed": [],
                "unused_allowlist_entries": [],
                "notified": False,
                "notification_delivery_error": None,
                "cache_hit": False,
            },
        }

        (gen_dir / ".provenance.json").write_text(json.dumps(manifest))

        different_hash = "sha256:" + "b" * 64

        result = provenance_checker.check_provenance(
            "comp-foo", different_hash, gate_versions, repo_root
        )

        hit = result.get("hit") if isinstance(result, dict) else getattr(result, "hit", None)
        verification_report = (
            result.get("verification_report")
            if isinstance(result, dict)
            else getattr(result, "verification_report", None)
        )
        license_scan = (
            result.get("license_scan")
            if isinstance(result, dict)
            else getattr(result, "license_scan", None)
        )
        secret_scan = (
            result.get("secret_scan")
            if isinstance(result, dict)
            else getattr(result, "secret_scan", None)
        )

        assert hit is False
        assert verification_report is None
        assert license_scan is None
        assert secret_scan is None