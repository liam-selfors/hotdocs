import json

import urllib.request

import secret_scanner


CACHE_MANAGER_SOURCE = '''
from dataclasses import dataclass
from typing import Any


@dataclass
class CacheKey:
    spec_bundle_hash: str
    gate_inputs_hash: str
    gate_version: str
    model_pin: str


@dataclass
class CachedResult:
    gate_type: str
    payload: Any
    stored_at: str


class Miss:
    pass


def get(cache_key, *, repo_root=None):
    return Miss()


def put(cache_key, result, *, repo_root=None):
    pass
'''

PATTERN_DB = {
    "version": "2.0.0",
    "rules": [
        {
            "rule_id": "aws-access-key-id",
            "risk_tier": "high",
            "pattern": "AKIA[0-9A-Z]{16}",
        }
    ],
}


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _make_repo(tmp_path):
    (tmp_path / "specs").mkdir()
    (tmp_path / "gen").mkdir()
    (tmp_path / "verification").mkdir()
    cache_manager_dir = tmp_path / "gen" / "cache-manager"
    cache_manager_dir.mkdir(parents=True)
    (cache_manager_dir / "cache_manager.py").write_text(CACHE_MANAGER_SOURCE)

    patterns_path = tmp_path / "secret-patterns.json"
    patterns_path.write_text(json.dumps(PATTERN_DB))
    return patterns_path


def _make_urlopen_recorder(record_path):
    def recorder(*args, **kwargs):
        with open(record_path, "a") as f:
            f.write("call\n")

        class _FakeResponse:
            def read(self):
                return b"{}"

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        return _FakeResponse()

    return recorder


def _count_calls(record_path):
    if not record_path.exists():
        return 0
    return len(record_path.read_text().splitlines())


def test_high_risk_match_notifies_independent_of_later_clean_retry(tmp_path, monkeypatch):
    _make_repo(tmp_path)
    monkeypatch.setenv("VAR_SECRET_PATTERNS_PATH", "secret-patterns.json")
    monkeypatch.setenv("VAR_COMPLIANCE_WEBHOOK_URL", "https://example.invalid/webhook")

    record_path = tmp_path / "urlopen_calls.log"
    monkeypatch.setattr(urllib.request, "urlopen", _make_urlopen_recorder(record_path))

    secret_dir = tmp_path / "gen" / "sample-component"
    secret_dir.mkdir(parents=True)
    secret_file = secret_dir / "config.py"
    secret_file.write_text("AWS_KEY = 'AKIAABCDEFGHIJKLMNOP'\n")

    result = secret_scanner.scan(tmp_path)

    assert _get(result, "flagged") is True
    assert _get(result, "notified") is True
    matches = _get(result, "matches")
    assert matches
    assert any(_get(m, "risk_tier") == "high" for m in matches)
    assert _get(result, "notification_delivery_error") is None
    assert _count_calls(record_path) == 1

    # A later retry that scans clean must not erase or duplicate the
    # notification already sent for the original flagged attempt.
    secret_file.write_text("AWS_KEY = 'not-a-secret'\n")
    retry_result = secret_scanner.scan(tmp_path)

    assert _get(retry_result, "flagged") is False
    assert _get(retry_result, "notified") is False
    assert _count_calls(record_path) == 1


def test_no_match_at_all_not_notified_urlopen_never_called(tmp_path, monkeypatch):
    _make_repo(tmp_path)
    monkeypatch.setenv("VAR_SECRET_PATTERNS_PATH", "secret-patterns.json")
    monkeypatch.setenv("VAR_COMPLIANCE_WEBHOOK_URL", "https://example.invalid/webhook")

    record_path = tmp_path / "urlopen_calls.log"
    monkeypatch.setattr(urllib.request, "urlopen", _make_urlopen_recorder(record_path))

    clean_dir = tmp_path / "gen" / "sample-component"
    clean_dir.mkdir(parents=True)
    (clean_dir / "config.py").write_text("GREETING = 'hello world'\n")

    result = secret_scanner.scan(tmp_path)

    assert _get(result, "flagged") is False
    assert _get(result, "notified") is False
    matches = _get(result, "matches")
    assert not matches
    assert _count_calls(record_path) == 0


def test_webhook_unset_high_risk_match_flagged_not_notified_no_urlopen(tmp_path, monkeypatch):
    _make_repo(tmp_path)
    monkeypatch.setenv("VAR_SECRET_PATTERNS_PATH", "secret-patterns.json")
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)

    record_path = tmp_path / "urlopen_calls.log"
    monkeypatch.setattr(urllib.request, "urlopen", _make_urlopen_recorder(record_path))

    secret_dir = tmp_path / "gen" / "sample-component"
    secret_dir.mkdir(parents=True)
    (secret_dir / "config.py").write_text("AWS_KEY = 'AKIAABCDEFGHIJKLMNOP'\n")

    result = secret_scanner.scan(tmp_path)

    assert _get(result, "flagged") is True
    assert _get(result, "notified") is False
    assert _get(result, "notification_delivery_error") is None
    matches = _get(result, "matches")
    assert matches
    assert _count_calls(record_path) == 0