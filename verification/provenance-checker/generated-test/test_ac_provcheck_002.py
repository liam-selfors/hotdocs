import json
from pathlib import Path

import pytest

import provenance_checker


H = "sha256:" + "a1" * 32
OTHER_H = "sha256:" + "b2" * 32

GATE_VERSIONS = {
    "compiler": "criterion-compiler@1.0.0",
    "generated_test": "generated_test@1.0.0",
    "verifier": "verifier-orchestrator@2.0.0",
    "license_scanner": "license_scanner@4.0.0-no-reference-corpus",
    "secret_scanner": "secret_scanner@3.1.0+detect-secrets.1.5.0",
}

VERIFICATION_REPORT = {
    "component_id": "comp-foo",
    "criteria": [
        {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"}
    ],
    "requirement_results": {"R-FOO-001": "pass"},
    "interface_drift": False,
    "mutation_score": 0.9,
    "overall": "pass",
}

LICENSE_SCAN = {
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

SECRET_SCAN = {
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


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _manifest():
    return {
        "spec_bundle_hash": H,
        "model_pin": "claude-sonnet-5",
        "prompt_version": "v1",
        "retry_feedback": None,
        "pipeline_version": "v1",
        "gate_versions": dict(GATE_VERSIONS),
        "provenance_hit": False,
        "generated_at": "2026-01-01T00:00:00Z",
        "verification_run_id": "run-123",
        "verification_report": VERIFICATION_REPORT,
        "license_scan": LICENSE_SCAN,
        "secret_scan": SECRET_SCAN,
    }


@pytest.fixture
def repo_root(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_TRUST_JUDGE_PROVENANCE", raising=False)
    root = tmp_path / "repo"
    manifest = json.dumps(_manifest(), indent=2)
    for sub in ("gen", "verification"):
        d = root / sub / "foo"
        d.mkdir(parents=True)
        (d / ".provenance.json").write_text(manifest, encoding="utf-8")
    return root


def test_ac_provcheck_002_different_spec_bundle_hash_is_definitive_miss(repo_root):
    # Given gen/foo/.provenance.json exists with spec_bundle_hash H
    manifest_path = repo_root / "gen" / "foo" / ".provenance.json"
    assert manifest_path.is_file()
    assert json.loads(manifest_path.read_text())["spec_bundle_hash"] == H

    # When check_provenance is called for comp-foo with a different spec_bundle_hash
    assert OTHER_H != H
    result = provenance_checker.check_provenance(
        "comp-foo", OTHER_H, dict(GATE_VERSIONS), Path(repo_root)
    )

    # Then hit is false and the three result fields are all null
    assert field(result, "hit") is False
    assert field(result, "verification_report") is None
    assert field(result, "license_scan") is None
    assert field(result, "secret_scan") is None


def test_ac_provcheck_002_control_matching_hash_is_hit(repo_root):
    # Control: the same manifest with the matching hash is honored, so the
    # miss above is caused by the hash difference, not by an unread manifest.
    result = provenance_checker.check_provenance(
        "comp-foo", H, dict(GATE_VERSIONS), Path(repo_root)
    )
    assert field(result, "hit") is True
    assert field(result, "verification_report") is not None