import json
import shutil
import tempfile
from pathlib import Path

import provenance_checker


def test_ac_provcheck_008():
    repo_root = Path(tempfile.mkdtemp())
    try:
        gen_dir = repo_root / "gen" / "foo"
        gen_dir.mkdir(parents=True)

        spec_bundle_hash = "sha256:" + "a" * 64

        manifest = {
            "spec_bundle_hash": spec_bundle_hash,
            "model_pin": "claude-sonnet-5",
            "prompt_version": "v1",
            "retry_feedback": None,
            "pipeline_version": "v1",
            "gate_versions": {"license_scanner": "1.0.0"},
            "provenance_hit": False,
            "generated_at": "2026-01-01T00:00:00Z",
            "verification_run_id": "run-123",
            "verification_report": {
                "component_id": "comp-foo",
                "criteria": [],
                "requirement_results": {},
                "interface_drift": False,
                "mutation_score": 1.0,
                "overall": "pass",
            },
            "license_scan": {
                "component_id": "comp-foo",
                "gate_version": "license_scanner@1.0.0",
                "evaluated": True,
                "reason": None,
                "similarity_score": 0.1,
                "block_threshold": 0.7,
                "blocked": False,
                "matches": [],
                "notified": False,
                "notification_delivery_error": None,
                "cache_hit": False,
            },
            "secret_scan": {
                "scope": "full",
                "gate_version": "secret_scanner@1.0.0",
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

        current_gate_versions = {"license_scanner": "2.0.0"}

        result = provenance_checker.check_provenance(
            "comp-foo", spec_bundle_hash, current_gate_versions, repo_root
        )

        hit = result.get("hit") if isinstance(result, dict) else getattr(result, "hit", None)
        assert hit is False

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

        assert verification_report is None
        assert license_scan is None
        assert secret_scan is None
    finally:
        shutil.rmtree(repo_root, ignore_errors=True)