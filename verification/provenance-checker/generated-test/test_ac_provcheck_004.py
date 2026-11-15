import json
from pathlib import Path

import provenance_checker


def field(value, name, default=None):
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


SPEC_BUNDLE_HASH = "sha256:" + "ab" * 32

GATE_VERSIONS = {
    "compiler": "criterion-compiler@1.0.0",
    "generated_test": "generated_test@1.0.0",
    "verifier": "verifier-orchestrator@2.0.0",
    "license_scanner": "license_scanner@4.0.0-no-reference-corpus",
    "secret_scanner": "secret_scanner@3.1.0+detect-secrets.1.5.0",
}


def _verification_report():
    return {
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
                "rationale": "The implementation satisfies the requirement.",
            },
        ],
        "requirement_results": {"R-FOO-001": "pass", "R-FOO-002": "pass"},
        "interface_drift": False,
        "mutation_score": 0.9,
        "overall": "pass",
    }


def _license_scan():
    return {
        "component_id": "comp-foo",
        "gate_version": GATE_VERSIONS["license_scanner"],
        "evaluated": False,
        "reason": "no-reference-corpus",
        "similarity_score": None,
        "block_threshold": None,
        "blocked": False,
        "matches": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }


def _secret_scan():
    return {
        "scope": "full",
        "gate_version": GATE_VERSIONS["secret_scanner"],
        "flagged": False,
        "matches": [],
        "allowed": [],
        "unused_allowlist_entries": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }


def _manifest():
    return {
        "spec_bundle_hash": SPEC_BUNDLE_HASH,
        "model_pin": "claude-sonnet-5",
        "prompt_version": "v1",
        "retry_feedback": None,
        "pipeline_version": "v1",
        "gate_versions": dict(GATE_VERSIONS),
        "provenance_hit": False,
        "generated_at": "2026-01-01T00:00:00Z",
        "verification_run_id": "run-123",
        "verification_report": _verification_report(),
        "license_scan": _license_scan(),
        "secret_scan": _secret_scan(),
    }


def _write_manifest(repo_root: Path):
    for sub in ("gen", "verification"):
        d = repo_root / sub / "foo"
        d.mkdir(parents=True, exist_ok=True)
        (d / ".provenance.json").write_text(
            json.dumps(_manifest(), indent=2), encoding="utf-8"
        )


def test_llm_judge_criterion_without_trust_is_a_miss(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write_manifest(repo_root)

    monkeypatch.setenv("VAR_TRUST_JUDGE_PROVENANCE", "false")
    try:
        result = provenance_checker.check_provenance(
            "comp-foo", SPEC_BUNDLE_HASH, dict(GATE_VERSIONS), repo_root
        )
    finally:
        monkeypatch.delenv("VAR_TRUST_JUDGE_PROVENANCE", raising=False)

    assert field(result, "hit") is False

    # A miss is definitive: nothing from the manifest is passed through.
    assert field(result, "verification_report") is None
    assert field(result, "license_scan") is None
    assert field(result, "secret_scan") is None