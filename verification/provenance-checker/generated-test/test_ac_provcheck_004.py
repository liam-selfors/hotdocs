import json
import os
from pathlib import Path

import provenance_checker


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


SPEC_BUNDLE_HASH = "sha256:" + "deadbeef" * 8

GATE_VERSIONS = {
    "compiler": "criterion-compiler@1.0.0",
    "generated_test": "generated_test@1.0.0",
    "verifier": "verifier-orchestrator@2.0.0",
    "license_scanner": "license_scanner@4.0.0",
    "secret_scanner": "secret_scanner@3.0.0+detect-secrets.1.5.0",
}

VERIFICATION_REPORT = {
    "component_id": "comp-foo",
    "criteria": [
        {
            "id": "AC-FOO-002",
            "covers": "R-FOO-002",
            "kind": "llm-judge",
            "result": "pass",
            "rationale": "looked fine",
        }
    ],
    "requirement_results": {"R-FOO-002": "pass"},
    "interface_drift": False,
    "mutation_score": 1.0,
    "overall": "pass",
}

LICENSE_SCAN = {
    "component_id": "comp-foo",
    "gate_version": "license_scanner@4.0.0",
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

SECRET_SCAN = {
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


def _write_manifest(repo_root: Path) -> None:
    gen_dir = repo_root / "gen" / "foo"
    gen_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "spec_bundle_hash": SPEC_BUNDLE_HASH,
        "model_pin": "claude-sonnet-5",
        "prompt_version": "v1",
        "retry_feedback": None,
        "pipeline_version": "v1",
        "gate_versions": GATE_VERSIONS,
        "provenance_hit": False,
        "generated_at": "2026-01-01T00:00:00Z",
        "verification_run_id": "run-123",
        "verification_report": VERIFICATION_REPORT,
        "license_scan": LICENSE_SCAN,
        "secret_scan": SECRET_SCAN,
    }
    (gen_dir / ".provenance.json").write_text(json.dumps(manifest))


def test_llm_judge_criterion_with_judge_provenance_untrusted_is_a_miss(tmp_path):
    _write_manifest(tmp_path)

    os.environ["VAR_TRUST_JUDGE_PROVENANCE"] = "false"
    try:
        result = provenance_checker.check_provenance(
            "comp-foo",
            SPEC_BUNDLE_HASH,
            dict(GATE_VERSIONS),
            tmp_path,
        )
    finally:
        del os.environ["VAR_TRUST_JUDGE_PROVENANCE"]

    assert _get(result, "hit") is False
    assert _get(result, "verification_report") is None
    assert _get(result, "license_scan") is None
    assert _get(result, "secret_scan") is None