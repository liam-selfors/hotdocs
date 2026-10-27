"""One test per AC-PROVCHECK-* criterion in
specs/components/provenance-checker/acceptance/."""

from conftest import write_manifest
from provenance_checker import check_provenance


def test_ac_provcheck_001_hit_no_llm_judge_returns_manifest_verbatim(repo_root):
    write_manifest(repo_root, "foo", spec_bundle_hash="H",
                    verification_report={"criteria": [{"kind": "generated-test"}]},
                    license_scan={"flagged": True}, secret_scan={"flagged": False})
    result = check_provenance("comp-foo", "H", {}, repo_root)
    assert result.hit is True
    assert result.verification_report == {"criteria": [{"kind": "generated-test"}]}
    assert result.license_scan == {"flagged": True}
    assert result.secret_scan == {"flagged": False}


def test_ac_provcheck_002_hash_mismatch_is_a_total_miss(repo_root):
    write_manifest(repo_root, "foo", spec_bundle_hash="H")
    result = check_provenance("comp-foo", "DIFFERENT", {}, repo_root)
    assert result.hit is False
    assert result.verification_report is None
    assert result.license_scan is None
    assert result.secret_scan is None


def test_ac_provcheck_003_missing_manifest_is_a_miss(repo_root):
    result = check_provenance("comp-foo", "H", {}, repo_root)
    assert result.hit is False


def test_ac_provcheck_004_llm_judge_with_trust_false_is_a_miss(repo_root, monkeypatch):
    write_manifest(repo_root, "foo", spec_bundle_hash="H",
                    verification_report={"criteria": [{"kind": "llm-judge"}]})
    monkeypatch.setenv("VAR_TRUST_JUDGE_PROVENANCE", "false")
    result = check_provenance("comp-foo", "H", {}, repo_root)
    assert result.hit is False


def test_ac_provcheck_005_llm_judge_with_trust_true_is_a_hit(repo_root, monkeypatch):
    write_manifest(repo_root, "foo", spec_bundle_hash="H",
                    verification_report={"criteria": [{"kind": "llm-judge"}]})
    monkeypatch.setenv("VAR_TRUST_JUDGE_PROVENANCE", "true")
    result = check_provenance("comp-foo", "H", {}, repo_root)
    assert result.hit is True


def test_ac_provcheck_005b_absent_var_defaults_to_true(repo_root):
    write_manifest(repo_root, "foo", spec_bundle_hash="H",
                    verification_report={"criteria": [{"kind": "llm-judge"}]})
    result = check_provenance("comp-foo", "H", {}, repo_root)
    assert result.hit is True  # absent means true (D1's cheap cold-regen default)


def test_ac_provcheck_006_read_only_never_touches_the_manifest(repo_root):
    path = write_manifest(repo_root, "foo", spec_bundle_hash="H")
    content_before = path.read_bytes()
    mtime_before = path.stat().st_mtime_ns

    check_provenance("comp-foo", "H", {}, repo_root)  # hit
    check_provenance("comp-foo", "WRONG", {}, repo_root)  # miss

    assert path.read_bytes() == content_before
    assert path.stat().st_mtime_ns == mtime_before
    assert list(repo_root.rglob("*")) == [repo_root / "gen", repo_root / "gen" / "foo", path]


def test_ac_provcheck_007_comparison_uses_exactly_the_caller_supplied_hash(repo_root):
    write_manifest(repo_root, "foo", spec_bundle_hash="H1")
    assert check_provenance("comp-foo", "H1", {}, repo_root).hit is True
    assert check_provenance("comp-foo", "H2", {}, repo_root).hit is False


def test_ac_provcheck_008_gate_version_mismatch_is_a_miss_even_with_matching_hash(repo_root):
    write_manifest(repo_root, "foo", spec_bundle_hash="H",
                    gate_versions={"license_scanner": "1.0.0"})
    result = check_provenance("comp-foo", "H", {"license_scanner": "2.0.0"}, repo_root)
    assert result.hit is False

    result_matching = check_provenance("comp-foo", "H", {"license_scanner": "1.0.0"}, repo_root)
    assert result_matching.hit is True
