import socket
import urllib.error
import urllib.request

import secret_scanner


def getf(obj, name, default=None):
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


AWS_KEY_LITERAL = "AKIA" + "IOSFODNN7EXAMPLE"


def _plant_high_risk_secret(tmp_path):
    target = tmp_path / "config.py"
    target.write_text(
        'AWS_ACCESS_KEY_ID = "%s"\n' % AWS_KEY_LITERAL,
        encoding="utf-8",
    )
    return target


def _run_scan(tmp_path, monkeypatch, urlopen_side_effect):
    monkeypatch.setenv("VAR_COMPLIANCE_WEBHOOK_URL", "https://example.invalid/webhook")

    def fake_urlopen(*args, **kwargs):
        raise urlopen_side_effect

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    target = _plant_high_risk_secret(tmp_path)
    return secret_scanner.scan_files([target], repo_root=tmp_path)


def _assert_high_risk_match_present(result):
    matches = getf(result, "matches")
    assert matches, "expected at least one match from the planted AWS key fixture"
    risk_tiers = [getf(m, "risk_tier") for m in matches]
    assert "high" in risk_tiers, "expected at least one high risk_tier match, got %r" % risk_tiers
    assert getf(result, "flagged") is True


def test_generic_network_error_sets_network_category(tmp_path, monkeypatch):
    result = _run_scan(tmp_path, monkeypatch, urllib.error.URLError("connection refused"))

    _assert_high_risk_match_present(result)

    assert getf(result, "notified") is True

    error = getf(result, "notification_delivery_error")
    assert error is not None
    assert getf(error, "category") == "network"
    message = getf(error, "message")
    assert isinstance(message, str) and message != ""

    assert getf(result, "flagged") is True


def test_http_401_sets_auth_category(tmp_path, monkeypatch):
    http_error = urllib.error.HTTPError(
        url="https://example.invalid/webhook",
        code=401,
        msg="Unauthorized",
        hdrs=None,
        fp=None,
    )
    result = _run_scan(tmp_path, monkeypatch, http_error)

    _assert_high_risk_match_present(result)

    assert getf(result, "notified") is True

    error = getf(result, "notification_delivery_error")
    assert error is not None
    assert getf(error, "category") == "auth"

    assert getf(result, "flagged") is True


def test_socket_timeout_sets_timeout_category(tmp_path, monkeypatch):
    result = _run_scan(tmp_path, monkeypatch, socket.timeout("timed out"))

    _assert_high_risk_match_present(result)

    assert getf(result, "notified") is True

    error = getf(result, "notification_delivery_error")
    assert error is not None
    assert getf(error, "category") == "timeout"

    assert getf(result, "flagged") is True


def test_http_500_sets_network_category(tmp_path, monkeypatch):
    http_error = urllib.error.HTTPError(
        url="https://example.invalid/webhook",
        code=500,
        msg="Internal Server Error",
        hdrs=None,
        fp=None,
    )
    result = _run_scan(tmp_path, monkeypatch, http_error)

    _assert_high_risk_match_present(result)

    assert getf(result, "notified") is True

    error = getf(result, "notification_delivery_error")
    assert error is not None
    assert getf(error, "category") == "network"

    assert getf(result, "flagged") is True