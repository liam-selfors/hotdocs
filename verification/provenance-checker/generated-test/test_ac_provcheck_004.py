import json

import provenance_checker


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


GATE_VERSIONS = {
    "compiler": "criterion-compiler@1.0.0",
    "generated_test": "generated_test@1.0.0",
    "verifier": "verifier-orchestrator@2.0.0",
    "license_scanner": "license_scanner@3.1.0",
    "secret_scanner": "secret_scanner@0.0.0",
}

SPEC_BUNDLE_HASH = "sha256:" + "a" * 64


def _write_provenance_manifest(repo_root, spec_bundle_hash, gate_versions):
    gen_dir = repo_root / "gen" / "foo"
    gen_dir.mkdir(parents=True, exist_ok=True)

    verification_report = {
        "component_id": "comp-foo",
        "criteria": [
            {
                "id": "AC-FOO-001",
                "covers": "R-FOO-001",
                "kind": "llm-judge",
                "result": "pass",
                "rationale": "matches expected behavior",
            }
        ],
        "requirement_results": {"R-FOO-001": "pass"},
        "interface_drift": False,
        "mutation_score": 1.0,
        "overall": "pass",
    }
    license_scan = {
        "component_id": "comp-foo",
        "gate_version": gate_versions["license_scanner"],
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
        "gate_version": gate_versions["secret_scanner"],
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
    (gen_dir / ".provenance.json").write_text(json.dumps(manifest))


def test_llm_judge_provenance_untrusted_forces_miss(tmp_path, monkeypatch):
    repo_root = tmp_path
    _write_provenance_manifest(repo_root, SPEC_BUNDLE_HASH, GATE_VERSIONS)

    monkeypatch.setenv("VAR_TRUST_JUDGE_PROVENANCE", "false")

    result = provenance_checker.check_provenance(
        "comp-foo", SPEC_BUNDLE_HASH, dict(GATE_VERSIONS), repo_root
    )

    assert _get(result, "hit") is False
    assert _get(result, "verification_report") is None
    assert _get(result, "license_scan") is None
    assert _get(result, "secret_scan") is None