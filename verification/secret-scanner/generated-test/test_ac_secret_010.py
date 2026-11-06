from pathlib import Path

import secret_scanner


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def test_quoted_secrets_detected_as_low_risk(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)

    repo_root = tmp_path / "repo"
    foo_dir = repo_root / "gen" / "foo"
    foo_dir.mkdir(parents=True)
    (foo_dir / "e.py").write_text(
        'token = "aB3dE5gH7jK9mN1pQ3sT5vW7yZ9bD1fH3jL5nP7r"\n'
        'sha = "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b"\n'
    )

    result = secret_scanner.scan(repo_root)

    matches = _get(result, "matches")
    assert matches is not None

    simplified = sorted(
        (
            _get(m, "file"),
            _get(m, "line"),
            _get(m, "rule_id"),
            _get(m, "risk_tier"),
        )
        for m in matches
    )

    assert simplified == [
        ("gen/foo/e.py", 1, "Base64 High Entropy String", "low"),
        ("gen/foo/e.py", 2, "Hex High Entropy String", "low"),
    ]

    assert bool(_get(result, "flagged")) is True


def test_unquoted_secret_is_a_known_gap_and_is_not_detected(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)

    repo_root = tmp_path / "repo"
    foo_dir = repo_root / "gen" / "foo"
    foo_dir.mkdir(parents=True)
    (foo_dir / "e.py").write_text(
        "token = aB3dE5gH7jK9mN1pQ3sT5vW7yZ9bD1fH3jL5nP7r\n"
    )

    result = secret_scanner.scan(repo_root)

    matches = _get(result, "matches")
    assert matches == []
    assert bool(_get(result, "flagged")) is False