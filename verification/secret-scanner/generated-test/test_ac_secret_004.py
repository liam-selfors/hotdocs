import os
import sys
import urllib.request
from pathlib import Path

import pytest

import secret_scanner


WEBHOOK_URL = "https://compliance.example.invalid/hotdocs-webhook"

# The planted AWS-access-key-shaped value is assembled at runtime from short
# fragments so this test file itself never carries the full recognizable shape.
_AWS_PREFIX = "AK" + "IA"
_AWS_BODY_A = "Q7XK2M9P"
_AWS_BODY_B = "LRT4VBNW"


def _planted_aws_key():
    return _AWS_PREFIX + _AWS_BODY_A + _AWS_BODY_B


FAKE_CACHE_MANAGER = '''\
import datetime
from dataclasses import dataclass


class SchemaValidationError(ValueError):
    pass


@dataclass
class CacheKey:
    spec_bundle_hash: str
    gate_inputs_hash: str
    gate_version: str
    model_pin: str


@dataclass
class CachedResult:
    gate_type: str
    payload: object
    stored_at: str


class Miss:
    def __eq__(self, other):
        return isinstance(other, Miss)

    def __hash__(self):
        return 0


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def get(cache_key, *, repo_root=None):
    return Miss()


def put(cache_key, result, *, repo_root=None):
    return None


def stats(*, repo_root=None):
    return {"entry_count": 0}
'''


def _field(value, name, default=None):
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


class _FakeResponse:
    status = 200
    code = 200

    def read(self, *args, **kwargs):
        return b""

    def getcode(self):
        return 200

    def close(self):
        return None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _install_recorder(monkeypatch):
    calls = []

    def recorder(*args, **kwargs):
        calls.append((args, kwargs))
        return _FakeResponse()

    monkeypatch.setattr(urllib.request, "urlopen", recorder)
    if hasattr(secret_scanner, "urlopen"):
        monkeypatch.setattr(secret_scanner, "urlopen", recorder, raising=False)
    return calls


def _call_url(call):
    args, kwargs = call
    target = args[0] if args else kwargs.get("url")
    if isinstance(target, str):
        return target
    full_url = getattr(target, "full_url", None)
    if full_url is not None:
        return full_url
    getter = getattr(target, "get_full_url", None)
    if callable(getter):
        return getter()
    return target


def _make_repo(tmp_path, with_secret):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    cm_dir = repo_root / "gen" / "cache-manager"
    cm_dir.mkdir(parents=True)
    (cm_dir / "cache_manager.py").write_text(FAKE_CACHE_MANAGER, encoding="utf-8")

    (repo_root / "README.md").write_text("hello world\n", encoding="utf-8")
    foo_dir = repo_root / "gen" / "foo"
    foo_dir.mkdir(parents=True)
    _write_config(repo_root, with_secret)
    return repo_root


def _write_config(repo_root, with_secret):
    config = repo_root / "gen" / "foo" / "config.py"
    if with_secret:
        config.write_text(
            "REGION = 'us-east-1'\n"
            "AWS_ACCESS_ID = '" + _planted_aws_key() + "'\n",
            encoding="utf-8",
        )
    else:
        config.write_text("REGION = 'us-east-1'\nVALUE = 1\n", encoding="utf-8")


@pytest.fixture
def clean_env(monkeypatch, tmp_path):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)
    monkeypatch.chdir(tmp_path)
    return monkeypatch


def _has_high_match(result):
    matches = _field(result, "matches") or []
    return any(_field(m, "risk_tier") == "high" for m in matches)


def test_high_risk_match_sends_notification_independent_of_later_clean_retry(
    clean_env, tmp_path
):
    monkeypatch = clean_env
    monkeypatch.setenv("VAR_COMPLIANCE_WEBHOOK_URL", WEBHOOK_URL)
    calls = _install_recorder(monkeypatch)

    repo_root = _make_repo(tmp_path, with_secret=True)

    first = secret_scanner.scan(repo_root)

    assert _field(first, "flagged") is True
    assert _has_high_match(first), _field(first, "matches")
    assert _field(first, "notified") is True
    assert _field(first, "notification_delivery_error") is None

    # The webhook call is attempted, and at most once.
    assert len(calls) == 1, calls
    assert _call_url(calls[0]) == WEBHOOK_URL

    # A later retry that scans clean never un-notifies the earlier one.
    _write_config(repo_root, with_secret=False)
    second = secret_scanner.scan(repo_root)

    assert _field(second, "flagged") is False
    assert not (_field(second, "matches") or [])
    assert _field(second, "notified") is False

    assert len(calls) == 1, calls
    assert _call_url(calls[0]) == WEBHOOK_URL
    assert _field(first, "notified") is True


def test_no_match_with_webhook_configured_never_notifies(clean_env, tmp_path):
    monkeypatch = clean_env
    monkeypatch.setenv("VAR_COMPLIANCE_WEBHOOK_URL", WEBHOOK_URL)
    calls = _install_recorder(monkeypatch)

    repo_root = _make_repo(tmp_path, with_secret=False)

    result = secret_scanner.scan(repo_root)

    assert _field(result, "flagged") is False
    assert not (_field(result, "matches") or [])
    assert _field(result, "notified") is False
    assert _field(result, "notification_delivery_error") is None
    assert calls == []


def test_high_match_without_webhook_configured_flags_but_never_notifies(
    clean_env, tmp_path
):
    monkeypatch = clean_env
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)
    calls = _install_recorder(monkeypatch)

    repo_root = _make_repo(tmp_path, with_secret=True)

    result = secret_scanner.scan(repo_root)

    assert _field(result, "flagged") is True
    assert _has_high_match(result), _field(result, "matches")
    assert _field(result, "notified") is False
    assert _field(result, "notification_delivery_error") is None
    assert calls == []