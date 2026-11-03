import json

import pytest

import provenance_checker


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


VALID_GATE_VERSIONS = {
    "compiler": "criterion-compiler@1.0.0",
    "generated_test": "generated_test@1.0.0",
    "verifier": "verifier-orchestrator@2.0.0",
    "license_scanner": "license_scanner@3.1.0",
    "secret_scanner": "secret_scanner@0.0.0",
}


@pytest.mark.parametrize(
    "spec_bundle_hash",
    [
        "sha256:" + "a" * 64,
        "sha256:deadbeef",
    ],
)
def test_miss_when_provenance_file_absent_no_component_dir(tmp_path, spec_bundle_hash):
    repo_root = tmp_path

    result = provenance_checker.check_provenance(
        "comp-foo", spec_bundle_hash, dict(VALID_GATE_VERSIONS), repo_root
    )

    assert _get(result, "hit") is False
    assert _get(result, "verification_report") is None
    assert _get(result, "license_scan") is None
    assert _get(result, "secret_scan") is None


def test_miss_when_provenance_file_absent_component_dir_exists(tmp_path):
    repo_root = tmp_path
    gen_dir = repo_root / "gen" / "foo"
    gen_dir.mkdir(parents=True)
    # Component dir exists but no .provenance.json inside it.
    (gen_dir / "some_other_file.txt").write_text("not a provenance manifest")

    result = provenance_checker.check_provenance(
        "comp-foo", "sha256:" + "b" * 64, dict(VALID_GATE_VERSIONS), repo_root
    )

    assert _get(result, "hit") is False
    assert _get(result, "verification_report") is None
    assert _get(result, "license_scan") is None
    assert _get(result, "secret_scan") is None


def test_miss_regardless_of_supplied_gate_versions_content(tmp_path):
    repo_root = tmp_path
    # gen/foo/.provenance.json deliberately absent.

    arbitrary_gate_versions = {
        "compiler": "whatever@9.9.9",
        "generated_test": "whatever@9.9.9",
        "verifier": "whatever@9.9.9",
        "license_scanner": "whatever@9.9.9",
        "secret_scanner": "whatever@9.9.9",
    }

    result = provenance_checker.check_provenance(
        "comp-foo", "sha256:" + "0" * 64, arbitrary_gate_versions, repo_root
    )

    assert _get(result, "hit") is False
    assert _get(result, "verification_report") is None
    assert _get(result, "license_scan") is None
    assert _get(result, "secret_scan") is None