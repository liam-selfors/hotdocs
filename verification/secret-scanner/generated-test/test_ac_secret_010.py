import pytest

import secret_scanner


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


ABOVE_THRESHOLD_STRING = "aabbccdefghijklmnopq"
BELOW_THRESHOLD_STRING = "aabbccddefghijklmnop"


def test_entropy_threshold_is_exactly_4_bits_per_char(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_SECRET_PATTERNS_PATH", raising=False)
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)

    repo_root = tmp_path
    specs_dir = repo_root / "specs"
    specs_dir.mkdir()
    (repo_root / "gen").mkdir()
    (repo_root / "verification").mkdir()

    above_file = specs_dir / "above_threshold.py"
    above_file.write_text(
        'token_above = "{}"\n'.format(ABOVE_THRESHOLD_STRING), encoding="utf-8"
    )

    below_file = specs_dir / "below_threshold.py"
    below_file.write_text(
        'token_below = "{}"\n'.format(BELOW_THRESHOLD_STRING), encoding="utf-8"
    )

    result = secret_scanner.scan(repo_root)

    matches = _get(result, "matches")
    assert matches is not None
    assert len(matches) == 1

    match = matches[0]
    assert _get(match, "rule_id") == "entropy-heuristic"
    assert _get(match, "risk_tier") == "low"
    assert _get(match, "file") == "specs/above_threshold.py"
    assert _get(match, "line") == 1

    matched_files = {_get(m, "file") for m in matches}
    assert "specs/below_threshold.py" not in matched_files