import socket
from urllib.error import HTTPError, URLError

import secret_scanner


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


AWS_EXAMPLE_KEY = "AKIAIOSFODNN7EXAMPLE"
WEBHOOK_URL = "https://webhook.example.invalid/notify"


def _make_repo_with_high_risk_secret(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / "config.py").write_text(
        'aws_access_key_id = "%s"\n' % AWS_EXAMPLE_KEY
    )
    return repo_root


def _run_scan_with_urlopen_error(monkeypatch, tmp_path, error):
    repo_root = _make_repo_with_high_risk_secret(tmp_path)
    monkeypatch.setenv("VAR_COMPLIANCE_WEBHOOK_URL", WEBHOOK_URL)

    calls = []

    def _raise(*args, **kwargs):
        calls.append((args, kwargs))
        raise error

    monkeypatch.setattr("urllib.request.urlopen", _raise)

    result = secret_scanner.scan(repo_root)
    return result, calls


def _assert_high_risk_match_present(result):
    matches = _get(result, "matches")
    assert matches
    assert any(_get(m, "risk_tier") == "high" for m in matches)


def test_network_error_sets_category_network(monkeypatch, tmp_path):
    result, calls = _run_scan_with_urlopen_error(
        monkeypatch, tmp_path, URLError("Network is unreachable")
    )

    assert len(calls) == 1
    _assert_high_risk_match_present(result)
    assert _get(result, "flagged") is True
    assert _get(result, "notified") is True

    error = _get(result, "notification_delivery_error")
    assert error is not None
    assert _get(error, "category") == "network"
    assert _get(error, "message")


def test_http_401_sets_category_auth(monkeypatch, tmp_path):
    http_error = HTTPError(WEBHOOK_URL, 401, "Unauthorized", None, None)
    result, calls = _run_scan_with_urlopen_error(monkeypatch, tmp_path, http_error)

    assert len(calls) == 1
    _assert_high_risk_match_present(result)
    assert _get(result, "flagged") is True
    assert _get(result, "notified") is True

    error = _get(result, "notification_delivery_error")
    assert error is not None
    assert _get(error, "category") == "auth"


def test_socket_timeout_sets_category_timeout(monkeypatch, tmp_path):
    result, calls = _run_scan_with_urlopen_error(
        monkeypatch, tmp_path, socket.timeout("timed out")
    )

    assert len(calls) == 1
    _assert_high_risk_match_present(result)
    assert _get(result, "flagged") is True
    assert _get(result, "notified") is True

    error = _get(result, "notification_delivery_error")
    assert error is not None
    assert _get(error, "category") == "timeout"


def test_http_500_sets_category_network(monkeypatch, tmp_path):
    http_error = HTTPError(WEBHOOK_URL, 500, "Internal Server Error", None, None)
    result, calls = _run_scan_with_urlopen_error(monkeypatch, tmp_path, http_error)

    assert len(calls) == 1
    _assert_high_risk_match_present(result)
    assert _get(result, "flagged") is True
    assert _get(result, "notified") is True

    error = _get(result, "notification_delivery_error")
    assert error is not None
    assert _get(error, "category") == "network"