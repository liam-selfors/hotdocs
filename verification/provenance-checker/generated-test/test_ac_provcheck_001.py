import json

import provenance_checker


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _build_manifest(spec_bundle_hash):
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
                "kind": "generated-test",
                "result": "pass",
                "test_authoring": {
                    "model": "gpt-5",
                    "seed": 0,
                    "prompt_version": "v1",
                    "cache_hit": False,
                },
            },
        ],
        "requirement_results": {"R-FOO-001": "pass", "R-FOO-002": "pass"},
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
        "block_threshold": 0.7,
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
    return {
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


def test_hash_match_with_no_llm_judge_criteria_is_unconditional_hit(tmp_path, monkeypatch):
    spec_bundle_hash = "sha256:" + "a" * 64
    manifest = _build_manifest(spec_bundle_hash)

    gen_dir = tmp_path / "gen" / "foo"
    gen_dir.mkdir(parents=True)
    (gen_dir / ".provenance.json").write_text(json.dumps(manifest))

    # The llm-judge-governing var is deliberately set to "false": since the
    # manifest's verification_report has no llm-judge-kind criterion, this
    # must have no bearing on the outcome (R-PROVCHECK-002's unless-clause
    # never engages here).
    monkeypatch.setenv("VAR_TRUST_JUDGE_PROVENANCE", "false")

    result = provenance_checker.check_provenance(
        component_id="comp-foo",
        spec_bundle_hash=spec_bundle_hash,
        gate_versions=manifest["gate_versions"],
        repo_root=tmp_path,
    )

    assert _get(result, "hit") is True
    assert _get(result, "verification_report") == manifest["verification_report"]
    assert _get(result, "license_scan") == manifest["license_scan"]
    assert _get(result, "secret_scan") == manifest["secret_scan"]