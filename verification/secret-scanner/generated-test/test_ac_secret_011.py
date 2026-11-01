import io
import json
import socket
import urllib.error
from unittest import mock

import pytest

import secret_scanner


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _make_repo(tmp_path):
    repo_root = tmp_path / "repo"
    (repo_root / "specs").mkdir(parents=True)
    (repo_root / "gen").mkdir(parents=True)
    (repo_root / "verification").mkdir(parents=True)

    patterns = {
        "version": "1.0.0",
        "rules": [
            {
                "rule_id": "fake-high-secret",
                "risk_tier": "high",
                "pattern": "FAKETOKEN-[0-9]{6}",
            }
        ],
    }
    (repo_root / "patterns.json").write_text(json.dumps(patterns))
    (repo_root / "specs" / "secret.txt").write_text("token = FAKETOKEN-123456\n")

    return repo_root


def _success_response():
    cm = mock.MagicMock()
    cm.__enter__.return_value = cm
    cm.__exit__.return_value = False
    cm.status = 200
    return cm


def _http_error(code):
    return urllib.error.HTTPError(
        url="https://example.invalid/webhook",
        code=code,
        msg="Error",
        hdrs=None,
        fp=io.BytesIO(b""),
    )


def test_network_error_sets_network_category_notified_and_flagged_unaffected(
    tmp_path, monkeypatch
):
    repo_root = _make_repo(tmp_path)
    monkeypatch.setenv("VAR_SECRET_PATTERNS_PATH", "patterns.json")
    monkeypatch.setenv("VAR_COMPLIANCE_WEBHOOK_URL", "https://example.invalid/webhook")

    with mock.patch("urllib.request.urlopen", return_value=_success_response()):
        baseline = secret_scanner.scan(repo_root)
    baseline_flagged = _get(baseline, "flagged")
    assert _get(baseline, "notified") is True

    with mock.patch(
        "urllib.request.urlopen",
        side_effect=urllib.error.URLError("connection refused"),
    ):
        result = secret_scanner.scan(repo_root)

    assert _get(result, "notified") is True
    error = _get(result, "notification_delivery_error")
    assert error is not None
    assert _get(error, "category") == "network"
    assert _get(result, "flagged") == baseline_flagged


def test_http_401_sets_auth_category(tmp_path, monkeypatch):
    repo_root = _make_repo(tmp_path)
    monkeypatch.setenv("VAR_SECRET_PATTERNS_PATH", "patterns.json")
    monkeypatch.setenv("VAR_COMPLIANCE_WEBHOOK_URL", "https://example.invalid/webhook")

    with mock.patch("urllib.request.urlopen", return_value=_success_response()):
        baseline = secret_scanner.scan(repo_root)
    baseline_flagged = _get(baseline, "flagged")

    with mock.patch("urllib.request.urlopen", side_effect=_http_error(401)):
        result = secret_scanner.scan(repo_root)

    assert _get(result, "notified") is True
    error = _get(result, "notification_delivery_error")
    assert error is not None
    assert _get(error, "category") == "auth"
    assert _get(result, "flagged") == baseline_flagged


def test_socket_timeout_sets_timeout_category(tmp_path, monkeypatch):
    repo_root = _make_repo(tmp_path)
    monkeypatch.setenv("VAR_SECRET_PATTERNS_PATH", "patterns.json")
    monkeypatch.setenv("VAR_COMPLIANCE_WEBHOOK_URL", "https://example.invalid/webhook")

    with mock.patch("urllib.request.urlopen", return_value=_success_response()):
        baseline = secret_scanner.scan(repo_root)
    baseline_flagged = _get(baseline, "flagged")

    with mock.patch(
        "urllib.request.urlopen", side_effect=socket.timeout("timed out")
    ):
        result = secret_scanner.scan(repo_root)

    assert _get(result, "notified") is True
    error = _get(result, "notification_delivery_error")
    assert error is not None
    assert _get(error, "category") == "timeout"
    assert _get(result, "flagged") == baseline_flagged


def test_http_500_sets_network_category(tmp_path, monkeypatch):
    repo_root = _make_repo(tmp_path)
    monkeypatch.setenv("VAR_SECRET_PATTERNS_PATH", "patterns.json")
    monkeypatch.setenv("VAR_COMPLIANCE_WEBHOOK_URL", "https://example.invalid/webhook")

    with mock.patch("urllib.request.urlopen", return_value=_success_response()):
        baseline = secret_scanner.scan(repo_root)
    baseline_flagged = _get(baseline, "flagged")

    with mock.patch("urllib.request.urlopen", side_effect=_http_error(500)):
        result = secret_scanner.scan(repo_root)

    assert _get(result, "notified") is True
    error = _get(result, "notification_delivery_error")
    assert error is not None
    assert _get(error, "category") == "network"
    assert _get(result, "flagged") == baseline_flagged