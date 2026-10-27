"""One test per AC-LICENSE-* criterion in
specs/components/license-scanner/acceptance/."""

import urllib.error

from conftest import real_hashes_for, write_corpus, write_gen_file
from license_scanner import scan

SOURCE_A = "\n".join(f"def function_{i}(): return {i} + value_{i}" for i in range(10))
SOURCE_B = "def totally_unrelated(): pass\n"


def test_ac_license_001_flagged_blocks(repo_root, monkeypatch):
    write_gen_file(repo_root, "foo", "main.py", SOURCE_A)
    real_hashes = real_hashes_for(repo_root, "foo")
    write_corpus(repo_root, [{"reference_id": "ref-1", "license_family": "gpl-3.0", "risk_tier": "high", "hashes": list(real_hashes)}])
    monkeypatch.setenv("VAR_LICENSE_CORPUS_PATH", str(repo_root / "reference-corpus.json"))

    result = scan("comp-foo", repo_root)
    assert result.blocked is True
    assert result.similarity_score >= result.block_threshold


def test_ac_license_002_clean_result_still_recorded(repo_root, monkeypatch):
    write_gen_file(repo_root, "foo", "main.py", SOURCE_B)
    write_corpus(repo_root, [])
    monkeypatch.setenv("VAR_LICENSE_CORPUS_PATH", str(repo_root / "reference-corpus.json"))

    result = scan("comp-foo", repo_root)
    assert result.blocked is False
    assert result.component_id == "comp-foo"
    assert result.similarity_score == 0.0


def test_ac_license_003_blocked_notifies_regardless_of_low_risk(repo_root, monkeypatch):
    write_gen_file(repo_root, "foo", "main.py", SOURCE_A)
    real_hashes = real_hashes_for(repo_root, "foo")
    write_corpus(repo_root, [{"reference_id": "ref-1", "license_family": "mit", "risk_tier": "low", "hashes": list(real_hashes)}])
    monkeypatch.setenv("VAR_LICENSE_CORPUS_PATH", str(repo_root / "reference-corpus.json"))
    monkeypatch.setenv("VAR_COMPLIANCE_WEBHOOK_URL", "https://hooks.example/x")
    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k: None)

    result = scan("comp-foo", repo_root)
    assert result.blocked is True
    assert result.notified is True


def test_ac_license_003b_high_risk_below_threshold_still_notifies(repo_root, monkeypatch):
    write_gen_file(repo_root, "foo", "main.py", SOURCE_A)
    real_hashes = list(real_hashes_for(repo_root, "foo"))
    partial = real_hashes[: max(1, len(real_hashes) // 2)]  # below block threshold, above reporting floor
    write_corpus(repo_root, [{"reference_id": "ref-1", "license_family": "agpl-3.0", "risk_tier": "high", "hashes": partial}], block_threshold=0.70)
    monkeypatch.setenv("VAR_LICENSE_CORPUS_PATH", str(repo_root / "reference-corpus.json"))
    monkeypatch.setenv("VAR_COMPLIANCE_WEBHOOK_URL", "https://hooks.example/x")
    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k: None)

    result = scan("comp-foo", repo_root)
    assert result.blocked is False
    assert result.notified is True


def test_ac_license_003c_blocked_but_no_webhook_configured(repo_root, monkeypatch):
    write_gen_file(repo_root, "foo", "main.py", SOURCE_A)
    real_hashes = real_hashes_for(repo_root, "foo")
    write_corpus(repo_root, [{"reference_id": "ref-1", "license_family": "mit", "risk_tier": "low", "hashes": list(real_hashes)}])
    monkeypatch.setenv("VAR_LICENSE_CORPUS_PATH", str(repo_root / "reference-corpus.json"))

    result = scan("comp-foo", repo_root)
    assert result.blocked is True
    assert result.notified is False


def test_ac_license_004_cache_hit_skips_rescan(repo_root, monkeypatch):
    write_gen_file(repo_root, "foo", "main.py", SOURCE_B)
    write_corpus(repo_root, [])
    monkeypatch.setenv("VAR_LICENSE_CORPUS_PATH", str(repo_root / "reference-corpus.json"))

    result1 = scan("comp-foo", repo_root)
    assert result1.cache_hit is False
    result2 = scan("comp-foo", repo_root)
    assert result2.cache_hit is True
    assert result2.similarity_score == result1.similarity_score


def test_ac_license_005_gate_version_bump_invalidates_cache(repo_root, monkeypatch):
    write_gen_file(repo_root, "foo", "main.py", SOURCE_B)
    write_corpus(repo_root, [], corpus_version=1)
    monkeypatch.setenv("VAR_LICENSE_CORPUS_PATH", str(repo_root / "reference-corpus.json"))
    result1 = scan("comp-foo", repo_root)
    assert "1" in result1.gate_version

    write_corpus(repo_root, [], corpus_version=2)
    result2 = scan("comp-foo", repo_root)
    assert result2.cache_hit is False
    assert "2" in result2.gate_version


def test_ac_license_006_exactly_one_result_per_scan(repo_root, monkeypatch):
    write_gen_file(repo_root, "foo", "main.py", SOURCE_B)
    write_corpus(repo_root, [])
    monkeypatch.setenv("VAR_LICENSE_CORPUS_PATH", str(repo_root / "reference-corpus.json"))
    result = scan("comp-foo", repo_root)
    assert result.component_id == "comp-foo"


def test_ac_license_008_eight_token_run_does_not_match(repo_root, monkeypatch):
    eight_tokens = "def f(): return a + b + c + d + e"  # fewer than 9 tokens total
    write_gen_file(repo_root, "foo", "main.py", eight_tokens)
    doc_hashes = real_hashes_for(repo_root, "foo")
    assert doc_hashes == set()  # too short for even one 9-token window

    write_corpus(repo_root, [{"reference_id": "ref-1", "license_family": "mit", "risk_tier": "low", "hashes": ["deadbeef" * 8]}])
    monkeypatch.setenv("VAR_LICENSE_CORPUS_PATH", str(repo_root / "reference-corpus.json"))
    result = scan("comp-foo", repo_root)
    assert result.similarity_score == 0.0
    assert result.blocked is False


def test_ac_license_009_webhook_failure_recorded_blocked_unaffected(repo_root, monkeypatch):
    write_gen_file(repo_root, "foo", "main.py", SOURCE_A)
    real_hashes = real_hashes_for(repo_root, "foo")
    write_corpus(repo_root, [{"reference_id": "ref-1", "license_family": "mit", "risk_tier": "low", "hashes": list(real_hashes)}])
    monkeypatch.setenv("VAR_LICENSE_CORPUS_PATH", str(repo_root / "reference-corpus.json"))
    monkeypatch.setenv("VAR_COMPLIANCE_WEBHOOK_URL", "https://hooks.example/x")

    def _raise(*a, **k):
        raise urllib.error.URLError("boom")
    monkeypatch.setattr("urllib.request.urlopen", _raise)

    result = scan("comp-foo", repo_root)
    assert result.notified is True
    assert result.notification_delivery_error is not None
    assert result.notification_delivery_error["category"] == "network"
    assert result.blocked is True
