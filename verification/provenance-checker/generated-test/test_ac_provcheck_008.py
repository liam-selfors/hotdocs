# hotdocs-criterion: sha256:76aa352ac9947a1a9f9093497548fb09c97d9f09cb37a9bf3c6e3198354b05f7
import json
from pathlib import Path

import provenance_checker


H = "sha256:" + "ab" * 32


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _manifest(gate_versions):
    return {
        "spec_bundle_hash": H,
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
                {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"}
            ],
            "requirement_results": {"R-FOO-001": "pass"},
            "interface_drift": False,
            "mutation_score": 0.92,
            "mutation_error": None,
            "overall": "pass",
        },
        "license_scan": {
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


def _write_manifest(repo_root, gate_versions):
    content = json.dumps(_manifest(gate_versions), indent=2)
    for sub in ("gen", "verification"):
        d = Path(repo_root) / sub / "foo"
        d.mkdir(parents=True, exist_ok=True)
        (d / ".provenance.json").write_text(content, encoding="utf-8")


def test_gate_version_mismatch_is_miss_even_when_spec_bundle_hash_matches(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_TRUST_JUDGE_PROVENANCE", raising=False)
    repo_root = tmp_path
    _write_manifest(repo_root, {"license_scanner": "1.0.0"})

    result = provenance_checker.check_provenance(
        "comp-foo", H, {"license_scanner": "2.0.0"}, repo_root
    )

    assert field(result, "hit") is False


def test_control_matching_gate_versions_and_hash_is_hit(tmp_path, monkeypatch):
    # Sanity control: the same manifest with matching gate_versions is a hit,
    # so the miss above is caused by the gate version difference alone.
    monkeypatch.delenv("VAR_TRUST_JUDGE_PROVENANCE", raising=False)
    repo_root = tmp_path
    _write_manifest(repo_root, {"license_scanner": "1.0.0"})

    result = provenance_checker.check_provenance(
        "comp-foo", H, {"license_scanner": "1.0.0"}, repo_root
    )

    assert field(result, "hit") is True