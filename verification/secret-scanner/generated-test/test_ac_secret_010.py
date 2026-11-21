# hotdocs-criterion: sha256:4751982422fa59e99fec0bf18f2d4bfded828af54ef6b64845f9fd74ce7d6bc6
import urllib.request
from pathlib import Path

import pytest

import secret_scanner


TOKEN = "aB3dE5gH7jK9mN1pQ3sT5vW7yZ9bD1fH3jL5nP7r"
SHA = "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


@pytest.fixture(autouse=True)
def _isolate_environment(monkeypatch):
    # No compliance webhook and no remote cache store: the scan stays local.
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)

    def _no_network(*args, **kwargs):
        raise AssertionError("urlopen must not be called in this test")

    monkeypatch.setattr(urllib.request, "urlopen", _no_network)


def _write(repo_root, rel, text):
    path = Path(repo_root) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_quoted_token_and_sha_yield_two_low_tier_matches(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    content = (
        "token = " + '"' + TOKEN + '"' + "\n"
        + "sha = " + '"' + SHA + '"' + "\n"
    )
    _write(repo_root, "gen/foo/e.py", content)

    result = secret_scanner.scan(repo_root)

    matches = list(field(result, "matches"))
    assert len(matches) == 2, matches

    summary = [
        (
            field(m, "file"),
            field(m, "line"),
            field(m, "rule_id"),
            field(m, "risk_tier"),
        )
        for m in matches
    ]
    assert summary == [
        ("gen/foo/e.py", 1, "Base64 High Entropy String", "low"),
        ("gen/foo/e.py", 2, "Hex High Entropy String", "low"),
    ]
    for m in matches:
        assert field(m, "risk_tier") == "low"


def test_unquoted_token_yields_no_matches(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    content = "token = " + TOKEN + "\n"
    _write(repo_root, "gen/foo/e.py", content)

    result = secret_scanner.scan(repo_root)

    matches = list(field(result, "matches"))
    assert matches == [], matches