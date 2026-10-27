"""One test per AC-SECRET-* criterion in
specs/components/secret-scanner/acceptance/."""

import urllib.error

from conftest import AWS_RULE, GENERIC_RULE, write_file, write_pattern_db
from secret_scanner import scan, scan_files

ENTROPY_ABOVE_4 = "zm6MqWbDq73Ttbz8qm25IqdN"  # ~4.0016 bits/char
ENTROPY_BELOW_4 = "RRmk6CZkMgkNRmSJ3tXjmrOe"  # ~3.9906 bits/char


def test_ac_secret_001_pattern_match_reported(repo_root, monkeypatch):
    write_pattern_db(repo_root, [AWS_RULE])
    monkeypatch.setenv("VAR_SECRET_PATTERNS_PATH", str(repo_root / "patterns.json"))
    write_file(repo_root, "gen/foo/config.py", "key = 'AKIAABCDEFGHIJKLMNOP'\n")

    result = scan(repo_root)
    assert any(m.file == "gen/foo/config.py" for m in result.matches)


def test_ac_secret_002_any_match_blocks(repo_root, monkeypatch):
    write_pattern_db(repo_root, [AWS_RULE])
    monkeypatch.setenv("VAR_SECRET_PATTERNS_PATH", str(repo_root / "patterns.json"))
    write_file(repo_root, "gen/foo/config.py", "key = 'AKIAABCDEFGHIJKLMNOP'\n")

    result = scan(repo_root)
    assert result.flagged is True


def test_ac_secret_003_clean_result_still_produced(repo_root, monkeypatch):
    write_pattern_db(repo_root, [AWS_RULE])
    monkeypatch.setenv("VAR_SECRET_PATTERNS_PATH", str(repo_root / "patterns.json"))
    write_file(repo_root, "gen/foo/config.py", "value = 'nothing interesting here'\n")

    result = scan(repo_root)
    assert result.flagged is False
    assert result.scope == "full"


def test_ac_secret_004_high_risk_notifies(repo_root, monkeypatch):
    write_pattern_db(repo_root, [AWS_RULE])
    monkeypatch.setenv("VAR_SECRET_PATTERNS_PATH", str(repo_root / "patterns.json"))
    monkeypatch.setenv("VAR_COMPLIANCE_WEBHOOK_URL", "https://hooks.example/x")
    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k: None)
    write_file(repo_root, "gen/foo/config.py", "key = 'AKIAABCDEFGHIJKLMNOP'\n")

    result = scan(repo_root)
    assert result.notified is True


def test_ac_secret_004b_low_risk_that_blocked_still_notifies(repo_root, monkeypatch):
    write_pattern_db(repo_root, [GENERIC_RULE])
    monkeypatch.setenv("VAR_SECRET_PATTERNS_PATH", str(repo_root / "patterns.json"))
    monkeypatch.setenv("VAR_COMPLIANCE_WEBHOOK_URL", "https://hooks.example/x")
    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k: None)
    write_file(repo_root, "gen/foo/config.py", "key = 'tok_AbCdEfGhIj'\n")

    result = scan(repo_root)
    assert result.flagged is True
    assert result.notified is True


def test_ac_secret_004c_clean_scan_never_notifies(repo_root, monkeypatch):
    write_pattern_db(repo_root, [AWS_RULE])
    monkeypatch.setenv("VAR_SECRET_PATTERNS_PATH", str(repo_root / "patterns.json"))
    monkeypatch.setenv("VAR_COMPLIANCE_WEBHOOK_URL", "https://hooks.example/x")
    write_file(repo_root, "gen/foo/config.py", "value = 'nothing interesting here'\n")

    result = scan(repo_root)
    assert result.notified is False


def test_ac_secret_005_cache_hit_skips_rescan(repo_root, monkeypatch):
    write_pattern_db(repo_root, [AWS_RULE])
    monkeypatch.setenv("VAR_SECRET_PATTERNS_PATH", str(repo_root / "patterns.json"))
    write_file(repo_root, "gen/foo/config.py", "value = 'nothing interesting here'\n")

    result1 = scan(repo_root)
    assert result1.cache_hit is False
    result2 = scan(repo_root)
    assert result2.cache_hit is True
    assert result2.flagged == result1.flagged


def test_ac_secret_006_gate_version_bump_invalidates_cache(repo_root, monkeypatch):
    path = write_pattern_db(repo_root, [AWS_RULE])
    monkeypatch.setenv("VAR_SECRET_PATTERNS_PATH", str(path))
    write_file(repo_root, "gen/foo/config.py", "value = 'nothing interesting here'\n")
    result1 = scan(repo_root)
    assert "1.0.0" in result1.gate_version

    import json
    data = json.loads(path.read_text())
    data["version"] = "2.0.0"
    path.write_text(json.dumps(data))

    result2 = scan(repo_root)
    assert result2.cache_hit is False
    assert "2.0.0" in result2.gate_version


def test_ac_secret_007_exactly_one_result(repo_root, monkeypatch):
    write_pattern_db(repo_root, [AWS_RULE])
    monkeypatch.setenv("VAR_SECRET_PATTERNS_PATH", str(repo_root / "patterns.json"))
    write_file(repo_root, "gen/foo/config.py", "value = 'clean'\n")
    result = scan(repo_root)
    assert result.scope == "full"


def test_ac_secret_008_precommit_scopes_to_given_files_no_cache(repo_root, monkeypatch):
    write_pattern_db(repo_root, [AWS_RULE])
    monkeypatch.setenv("VAR_SECRET_PATTERNS_PATH", str(repo_root / "patterns.json"))
    flagged_file = write_file(repo_root, "gen/foo/config.py", "key = 'AKIAABCDEFGHIJKLMNOP'\n")
    write_file(repo_root, "gen/bar/other.py", "key = 'AKIAABCDEFGHIJKLMNOP'\n")  # NOT passed

    result = scan_files([flagged_file])
    assert result.scope == "precommit"
    assert result.cache_hit is False
    assert result.gate_version is None
    assert all(m.file == str(flagged_file) for m in result.matches)


def test_ac_secret_010_entropy_threshold_is_exactly_4_0(repo_root, monkeypatch):
    write_pattern_db(repo_root, [])
    monkeypatch.setenv("VAR_SECRET_PATTERNS_PATH", str(repo_root / "patterns.json"))
    write_file(repo_root, "gen/foo/above.py", f"token = '{ENTROPY_ABOVE_4}'\n")
    write_file(repo_root, "gen/foo/below.py", f"token = '{ENTROPY_BELOW_4}'\n")

    result = scan(repo_root)
    flagged_files = {m.file for m in result.matches}
    assert "gen/foo/above.py" in flagged_files
    assert "gen/foo/below.py" not in flagged_files
    above_match = next(m for m in result.matches if m.file == "gen/foo/above.py")
    assert above_match.risk_tier == "low"


def test_ac_secret_011_webhook_failure_recorded_flagged_unaffected(repo_root, monkeypatch):
    write_pattern_db(repo_root, [AWS_RULE])
    monkeypatch.setenv("VAR_SECRET_PATTERNS_PATH", str(repo_root / "patterns.json"))
    monkeypatch.setenv("VAR_COMPLIANCE_WEBHOOK_URL", "https://hooks.example/x")

    def _raise(*a, **k):
        raise urllib.error.URLError("boom")
    monkeypatch.setattr("urllib.request.urlopen", _raise)
    write_file(repo_root, "gen/foo/config.py", "key = 'AKIAABCDEFGHIJKLMNOP'\n")

    result = scan(repo_root)
    assert result.notified is True
    assert result.notification_delivery_error is not None
    assert result.notification_delivery_error["category"] == "network"
    assert result.flagged is True
