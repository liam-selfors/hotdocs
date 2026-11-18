# hotdocs-criterion: sha256:a14b581ab6248bc4a67637e2e8529cb18a904ffb26af1ffbe97c42c0a60236c9
import hashlib
import json
import os
from pathlib import Path

import provenance_checker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _as_plain(value):
    if value is None or isinstance(value, (dict, list, str, int, float, bool)):
        return value
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        return to_dict()
    return value


def test_hash_match_with_llm_judge_criterion_and_trust_true_is_hit(tmp_path):
    repo_root = Path(tmp_path)
    spec_bundle_hash = "sha256:" + hashlib.sha256(b"ac-provcheck-005 bundle").hexdigest()

    gate_versions = {
        "compiler": "criterion-compiler@1.0.0",
        "generated_test": "generated_test@1.1.0",
        "verifier": "verifier-orchestrator@2.2.0",
        "license_scanner": "license_scanner@4.0.0-no-reference-corpus",
        "secret_scanner": "secret_scanner@3.1.0+detect-secrets.1.5.0",
    }

    verification_report = {
        "component_id": "comp-foo",
        "criteria": [
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"},
            {
                "id": "AC-FOO-002",
                "covers": "R-FOO-002",
                "kind": "llm-judge",
                "result": "pass",
                "rationale": "looks right",
            },
        ],
        "requirement_results": {"R-FOO-001": "pass", "R-FOO-002": "pass"},
        "interface_drift": False,
        "mutation_score": 0.9,
        "mutation_error": None,
        "overall": "pass",
    }
    license_scan = {
        "component_id": "comp-foo",
        "gate_version": "license_scanner@4.0.0-no-reference-corpus",
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
    secret_scan = {
        "scope": "full",
        "gate_version": "secret_scanner@3.1.0+detect-secrets.1.5.0",
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

    for sub in ("gen", "verification"):
        d = repo_root / sub / "foo"
        d.mkdir(parents=True, exist_ok=True)
        (d / ".provenance.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    previous = os.environ.get("VAR_TRUST_JUDGE_PROVENANCE")
    os.environ["VAR_TRUST_JUDGE_PROVENANCE"] = "true"
    try:
        result = provenance_checker.check_provenance(
            "comp-foo", spec_bundle_hash, dict(gate_versions), repo_root
        )
    finally:
        if previous is None:
            os.environ.pop("VAR_TRUST_JUDGE_PROVENANCE", None)
        else:
            os.environ["VAR_TRUST_JUDGE_PROVENANCE"] = previous

    assert "VAR_TRUST_JUDGE_PROVENANCE" not in os.environ or previous is not None

    assert field(result, "hit") is True
    assert _as_plain(field(result, "verification_report")) == verification_report
    assert _as_plain(field(result, "license_scan")) == license_scan
    assert _as_plain(field(result, "secret_scan")) == secret_scan