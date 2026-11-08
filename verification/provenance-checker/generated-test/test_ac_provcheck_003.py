from pathlib import Path

import provenance_checker


def test_check_provenance_reports_miss_when_manifest_absent(tmp_path: Path) -> None:
    repo_root = tmp_path
    component_id = "comp-foo"
    spec_bundle_hash = "sha256:" + "a" * 64
    gate_versions = {
        "compiler": "criterion-compiler@1.0.0",
        "generated_test": "generated_test@1.0.0",
        "verifier": "verifier-orchestrator@2.0.0",
        "license_scanner": "license_scanner@4.0.3+9f2c41ab07de",
        "secret_scanner": "secret_scanner@0.0.0",
    }

    manifest_path = repo_root / "gen" / "foo" / ".provenance.json"
    assert not manifest_path.exists()

    result = provenance_checker.check_provenance(
        component_id, spec_bundle_hash, gate_versions, repo_root
    )

    hit = result.get("hit") if isinstance(result, dict) else getattr(result, "hit", None)
    assert hit is False

    verification_report = (
        result.get("verification_report")
        if isinstance(result, dict)
        else getattr(result, "verification_report", None)
    )
    license_scan = (
        result.get("license_scan")
        if isinstance(result, dict)
        else getattr(result, "license_scan", None)
    )
    secret_scan = (
        result.get("secret_scan")
        if isinstance(result, dict)
        else getattr(result, "secret_scan", None)
    )

    assert verification_report is None
    assert license_scan is None
    assert secret_scan is None