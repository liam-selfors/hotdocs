"""AC-PROVCHECK-008 (Covers: R-PROVCHECK-001).

Given gen/foo/.provenance.json exists with spec_bundle_hash H and
gate_versions {"license_scanner": "1.0.0"}, but the caller's current
gate_versions is {"license_scanner": "2.0.0"}
When check_provenance is called for comp-foo with spec_bundle_hash H
Then the result's hit is false, even though spec_bundle_hash matches
"""

import json
from pathlib import Path

import provenance_checker


H = "sha256:" + "0123456789abcdef" * 4


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write_manifest(repo_root: Path, gate_versions: dict) -> Path:
    manifest = {
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
                {
                    "id": "AC-FOO-001",
                    "covers": "R-FOO-001",
                    "kind": "compiled",
                    "result": "pass",
                }
            ],
            "requirement_results": {"R-FOO-001": "pass"},
            "interface_drift": False,
            "mutation_score": 0.92,
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
    path = repo_root / "gen" / "foo" / ".provenance.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return path


def test_gate_version_mismatch_is_a_miss_even_when_hash_matches(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_TRUST_JUDGE_PROVENANCE", raising=False)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write_manifest(repo_root, {"license_scanner": "1.0.0"})

    result = provenance_checker.check_provenance(
        "comp-foo", H, {"license_scanner": "2.0.0"}, repo_root
    )

    assert field(result, "hit") is False


def test_control_same_manifest_with_matching_gate_versions_is_a_hit(tmp_path, monkeypatch):
    # Control: proves the manifest above is found and its spec_bundle_hash
    # matches, so the miss in the main test is due to gate_versions alone.
    monkeypatch.delenv("VAR_TRUST_JUDGE_PROVENANCE", raising=False)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write_manifest(repo_root, {"license_scanner": "1.0.0"})

    result = provenance_checker.check_provenance(
        "comp-foo", H, {"license_scanner": "1.0.0"}, repo_root
    )

    assert field(result, "hit") is True