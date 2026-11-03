import json

import provenance_checker


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def test_mismatched_spec_bundle_hash_is_definitive_miss(tmp_path):
    repo_root = tmp_path
    gen_dir = repo_root / "gen" / "foo"
    gen_dir.mkdir(parents=True)

    stored_gate_versions = {
        "compiler": "criterion-compiler@1.0.0",
        "generated_test": "generated_test@1.0.0",
        "verifier": "verifier-orchestrator@2.0.0",
        "license_scanner": "license_scanner@3.1.0",
        "secret_scanner": "secret_scanner@0.0.0",
    }
    stored_hash = "sha256:" + "a" * 64

    manifest = {
        "spec_bundle_hash": stored_hash,
        "model_pin": "claude-sonnet-5",
        "prompt_version": "v1",
        "retry_feedback": None,
        "pipeline_version": "v1",
        "gate_versions": stored_gate_versions,
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
            "gate_version": "license_scanner@3.1.0",
            "evaluated": True,
            "reason": None,
            "similarity_score": 0.0,
            "block_threshold": 0.70,
            "blocked": False,
            "matches": [],
            "notified": False,
            "notification_delivery_error": None,
            "cache_hit": False,
        },
        "secret_scan": {
            "scope": "full",
            "gate_version": "secret_scanner@3.0.0+detect-secrets.1.5.0",
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
        "comp-foo", different_hash, stored_gate_versions, repo_root
    )

    assert _get(result, "hit") is False
    assert _get(result, "verification_report") is None
    assert _get(result, "license_scan") is None
    assert _get(result, "secret_scan") is None