import json

import pytest

import provenance_checker


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def test_hash_match_with_no_llm_judge_criteria_is_honored_as_hit(tmp_path, monkeypatch):
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
                "kind": "generated-test",
                "result": "pass",
                "test_authoring": {
                    "model": "gpt-5",
                    "seed": 0,
                    "prompt_version": "v1",
                    "cache_hit": True,
                },
            },
        ],
        "requirement_results": {"R-FOO-001": "pass", "R-FOO-002": "pass"},
        "interface_drift": False,
        "mutation_score": 0.95,
        "overall": "pass",
    }

    license_scan = {
        "component_id": "comp-foo",
        "gate_version": "license_scanner@3.1.0",
        "similarity_score": 0.1,
        "block_threshold": 0.70,
        "blocked": False,
        "matches": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": True,
    }

    secret_scan = {
        "scope": "full",
        "gate_version": "secret_scanner@2.0.0",
        "flagged": False,
        "matches": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": True,
    }

    manifest = {
        "component_id": "comp-foo",
        "spec_bundle_hash": spec_bundle_hash,
        "gate_versions": gate_versions,
        "verification_report": verification_report,
        "license_scan": license_scan,
        "secret_scan": secret_scan,
    }

    gen_dir = tmp_path / "gen" / "foo"
    gen_dir.mkdir(parents=True)
    (gen_dir / ".provenance.json").write_text(json.dumps(manifest), encoding="utf-8")

    # No llm-judge-kind criteria are present, so the hit must be honored even
    # when VAR-TRUST-JUDGE-PROVENANCE resolves to false (R-PROVCHECK-002).
    monkeypatch.setenv("VAR_TRUST_JUDGE_PROVENANCE", "false")

    result = provenance_checker.check_provenance(
        "comp-foo", spec_bundle_hash, gate_versions, tmp_path
    )

    assert _get(result, "hit") is True
    assert _get(result, "verification_report") == verification_report
    assert _get(result, "license_scan") == license_scan
    assert _get(result, "secret_scan") == secret_scan