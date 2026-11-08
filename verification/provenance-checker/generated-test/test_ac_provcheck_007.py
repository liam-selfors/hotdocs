import json
import tempfile
from pathlib import Path

import provenance_checker


def _write_manifest(repo_root: Path, spec_bundle_hash: str, gate_versions: dict) -> dict:
    gen_dir = repo_root / "gen" / "foo"
    gen_dir.mkdir(parents=True, exist_ok=True)
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
    return manifest


def _field(value, name):
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def test_check_provenance_compares_only_caller_supplied_hash_against_manifest_field():
    manifest_hash = "sha256:" + "a" * 64
    different_caller_hash = "sha256:" + "b" * 64
    gate_versions = {
        "compiler": "criterion-compiler@1.0.0",
        "generated_test": "generated_test@1.0.0",
        "verifier": "verifier-orchestrator@2.0.0",
        "license_scanner": "license_scanner@4.0.3+9f2c41ab07de",
        "secret_scanner": "secret_scanner@0.0.0",
    }

    with tempfile.TemporaryDirectory() as tmp:
        repo_root = Path(tmp)
        manifest = _write_manifest(repo_root, manifest_hash, gate_versions)

        hit_result = provenance_checker.check_provenance(
            "comp-foo", manifest_hash, gate_versions, repo_root
        )
        assert _field(hit_result, "hit") is True
        assert _field(hit_result, "verification_report") == manifest["verification_report"]
        assert _field(hit_result, "license_scan") == manifest["license_scan"]
        assert _field(hit_result, "secret_scan") == manifest["secret_scan"]

        miss_result = provenance_checker.check_provenance(
            "comp-foo", different_caller_hash, gate_versions, repo_root
        )
        assert _field(miss_result, "hit") is False
        assert _field(miss_result, "verification_report") is None
        assert _field(miss_result, "license_scan") is None
        assert _field(miss_result, "secret_scan") is None