from pathlib import Path

import provenance_checker


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def test_miss_when_provenance_file_absent(tmp_path):
    repo_root = tmp_path

    provenance_path = repo_root / "gen" / "foo" / ".provenance.json"
    assert not provenance_path.exists()

    result = provenance_checker.check_provenance(
        component_id="comp-foo",
        spec_bundle_hash="sha256:abc123def456",
        gate_versions={
            "compiler": "criterion-compiler@1.0.0",
            "generated_test": "generated_test@1.0.0",
            "verifier": "verifier-orchestrator@2.0.0",
            "license_scanner": "license_scanner@3.1.0",
            "secret_scanner": "secret_scanner@0.0.0",
        },
        repo_root=repo_root,
    )

    assert _get(result, "hit") is False
    assert _get(result, "verification_report") is None
    assert _get(result, "license_scan") is None
    assert _get(result, "secret_scan") is None


def test_miss_when_provenance_file_absent_different_hash(tmp_path):
    repo_root = tmp_path

    provenance_path = repo_root / "gen" / "foo" / ".provenance.json"
    assert not provenance_path.exists()

    result = provenance_checker.check_provenance(
        component_id="comp-foo",
        spec_bundle_hash="sha256:0000111122223333",
        gate_versions={
            "compiler": "criterion-compiler@9.9.9",
            "generated_test": "generated_test@9.9.9",
            "verifier": "verifier-orchestrator@9.9.9",
            "license_scanner": "license_scanner@9.9.9",
            "secret_scanner": "secret_scanner@9.9.9",
        },
        repo_root=repo_root,
    )

    assert _get(result, "hit") is False
    assert _get(result, "verification_report") is None
    assert _get(result, "license_scan") is None
    assert _get(result, "secret_scan") is None