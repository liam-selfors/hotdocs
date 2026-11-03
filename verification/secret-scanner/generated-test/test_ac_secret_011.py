import socket
import urllib.error
import urllib.request

import pytest

import secret_scanner


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


AWS_KEY_FIXTURE = 'AWS_ACCESS_KEY_ID = "AKIAIOSFODNN7EXAMPLE"\n'


@pytest.fixture
def repo_with_high_risk_secret(tmp_path, monkeypatch):
    secret_file = tmp_path / "secrets.txt"
    secret_file.write_text(AWS_KEY_FIXTURE)
    monkeypatch.setenv("VAR_COMPLIANCE_WEBHOOK_URL", "https://example.invalid/webhook")
    return tmp_path, secret_file


def _assert_common(result, expected_category):
    matches = _get(result, "matches")
    assert matches, "expected the planted AWS key to produce a match"
    assert any(
        _get(m, "rule_id") == "AWS Access Key" and _get(m, "risk_tier") == "high"
        for m in matches
    ), "expected a high risk_tier match for the planted AWS key"

    assert _get(result, "flagged") is True
    assert _get(result, "notified") is True

    error = _get(result, "notification_delivery_error")
    assert error is not None
    assert _get(error, "category") == expected_category
    assert _get(error, "message")


def test_generic_network_error_yields_network_category(repo_with_high_risk_secret, monkeypatch):
    repo_root, secret_file = repo_with_high_risk_secret
    calls = []

    def _raise(*args, **kwargs):
        calls.append((args, kwargs))
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr(urllib.request, "urlopen", _raise)

    result = secret_scanner.scan_files([secret_file], repo_root=repo_root)

    _assert_common(result, "network")
    assert len(calls) == 1


def test_http_401_yields_auth_category(repo_with_high_risk_secret, monkeypatch):
    repo_root, secret_file = repo_with_high_risk_secret
    calls = []

    def _raise(*args, **kwargs):
        calls.append((args, kwargs))
        raise urllib.error.HTTPError(
            "https://example.invalid/webhook", 401, "Unauthorized", None, None
        )

    monkeypatch.setattr(urllib.request, "urlopen", _raise)

    result = secret_scanner.scan_files([secret_file], repo_root=repo_root)

    _assert_common(result, "auth")
    assert len(calls) == 1


def test_socket_timeout_yields_timeout_category(repo_with_high_risk_secret, monkeypatch):
    repo_root, secret_file = repo_with_high_risk_secret
    calls = []

    def _raise(*args, **kwargs):
        calls.append((args, kwargs))
        raise socket.timeout("timed out")

    monkeypatch.setattr(urllib.request, "urlopen", _raise)

    result = secret_scanner.scan_files([secret_file], repo_root=repo_root)

    _assert_common(result, "timeout")
    assert len(calls) == 1


def test_http_500_yields_network_category(repo_with_high_risk_secret, monkeypatch):
    repo_root, secret_file = repo_with_high_risk_secret
    calls = []

    def _raise(*args, **kwargs):
        calls.append((args, kwargs))
        raise urllib.error.HTTPError(
            "https://example.invalid/webhook", 500, "Internal Server Error", None, None
        )

    monkeypatch.setattr(urllib.request, "urlopen", _raise)

    result = secret_scanner.scan_files([secret_file], repo_root=repo_root)

    _assert_common(result, "network")
    assert len(calls) == 1