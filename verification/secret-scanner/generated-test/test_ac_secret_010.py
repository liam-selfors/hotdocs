# hotdocs-criterion: sha256:5b603edac327352a5a981ae8066999ed6d10b5f8de5f84e73307e2efd69da147
"""AC-SECRET-010: high-entropy findings are low-tier; unquoted token is a known gap."""

import urllib.request
from pathlib import Path

import pytest

import secret_scanner


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


# Built from short chunks so this test file itself holds no long
# random-looking literal for a scanner to flag.
TOKEN = "".join([
    "aB3dE5", "gH7jK9", "mN1pQ3", "sT5vW7", "yZ9bD1", "fH3jL5", "nP7r",
])
SHA = "".join([
    "9f86d0", "81884c", "7d659a", "2feaa0", "c55ad0", "15a3bf", "4f1b",
])


FAKE_CACHE_MANAGER = "\n".join([
    "from dataclasses import dataclass",
    "from datetime import datetime, timezone",
    "",
    "",
    "@dataclass",
    "class CacheKey:",
    "    spec_bundle_hash: str",
    "    gate_inputs_hash: str",
    "    gate_version: str",
    "    model_pin: str",
    "",
    "",
    "@dataclass",
    "class CachedResult:",
    "    gate_type: str",
    "    payload: dict",
    "    stored_at: str",
    "",
    "",
    "class Miss:",
    "    def __eq__(self, other):",
    "        return isinstance(other, Miss)",
    "",
    "    def __hash__(self):",
    "        return 0",
    "",
    "",
    "class SchemaValidationError(ValueError):",
    "    pass",
    "",
    "",
    "def get(cache_key, *, repo_root=None):",
    "    return Miss()",
    "",
    "",
    "def put(cache_key, result, *, repo_root=None):",
    "    return None",
    "",
    "",
    "def now_iso():",
    "    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')",
    "",
    "",
    "def stats(*, repo_root=None):",
    "    return dict(entry_count=0)",
    "",
])


def _make_repo(root: Path, content: str) -> Path:
    cache_dir = root / "gen" / "cache-manager"
    cache_dir.mkdir(parents=True)
    (cache_dir / "cache_manager.py").write_text(FAKE_CACHE_MANAGER, encoding="utf-8")
    target = root / "gen" / "foo" / "e.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return root


@pytest.fixture(autouse=True)
def _isolate(monkeypatch):
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)

    def _no_network(*args, **kwargs):
        raise AssertionError("no webhook call expected")

    monkeypatch.setattr(urllib.request, "urlopen", _no_network)


def test_quoted_high_entropy_strings_are_low_tier(tmp_path):
    content = 'token = "' + TOKEN + '"\n' + 'sha = "' + SHA + '"\n'
    repo_root = _make_repo(tmp_path / "repo", content)

    result = secret_scanner.scan(repo_root)
    matches = list(field(result, "matches"))

    assert len(matches) == 2, matches

    first, second = matches
    assert field(first, "file") == "gen/foo/e.py"
    assert field(first, "line") == 1
    assert field(first, "rule_id") == "Base64 High Entropy String"
    assert field(first, "risk_tier") == "low"

    assert field(second, "file") == "gen/foo/e.py"
    assert field(second, "line") == 2
    assert field(second, "rule_id") == "Hex High Entropy String"
    assert field(second, "risk_tier") == "low"


def test_unquoted_token_is_not_found(tmp_path):
    content = "token = " + TOKEN + "\n"
    repo_root = _make_repo(tmp_path / "repo", content)

    result = secret_scanner.scan(repo_root)
    matches = list(field(result, "matches"))

    assert matches == [], matches