# hotdocs-criterion: sha256:1407dfd3f40580e3249bccf05725c607d02369093c18d4aa0c4cb0c10b1006a6
import secret_scanner

import socket
import urllib.error
import urllib.request
from email.message import Message
from pathlib import Path

import pytest


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


WEBHOOK_URL = "http://compliance.example.invalid/hook"


def _write_fixture(repo_root):
    # Built by concatenation so this test file itself never holds a
    # contiguous key-shaped literal.
    key = "AKIA" + "IOSFODNN7" + "EXAMPLE"
    target = Path(repo_root) / "gen" / "foo" / "config.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("aws_access_key_id = " + repr(key) + "\n")
    return target


def _http_error(code):
    return urllib.error.HTTPError(WEBHOOK_URL, code, "error", Message(), None)


def _raiser(kind):
    if kind == "network":
        return urllib.error.URLError("connection refused")
    if kind == "auth401":
        return _http_error(401)
    if kind == "timeout":
        return socket.timeout("timed out")
    if kind == "http500":
        return _http_error(500)
    raise AssertionError(kind)


def _install_failing_urlopen(monkeypatch, kind, calls):
    def fake_urlopen(*args, **kwargs):
        calls.append(1)
        raise _raiser(kind)

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    if hasattr(secret_scanner, "urlopen"):
        monkeypatch.setattr(secret_scanner, "urlopen", fake_urlopen)


def _baseline_flagged(tmp_path, monkeypatch, target):
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)
    calls = []

    def fake_urlopen(*args, **kwargs):
        calls.append(1)
        raise AssertionError("webhook must not be called when unconfigured")

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    if hasattr(secret_scanner, "urlopen"):
        monkeypatch.setattr(secret_scanner, "urlopen", fake_urlopen)
    result = secret_scanner.scan_files([target], repo_root=tmp_path)
    return field(result, "flagged")


@pytest.mark.parametrize(
    "kind, expected_category",
    [
        ("network", "network"),
        ("auth401", "auth"),
        ("timeout", "timeout"),
        ("http500", "network"),
    ],
)
def test_webhook_failure_is_recorded_not_raised(tmp_path, monkeypatch, kind, expected_category):
    target = _write_fixture(tmp_path)

    baseline_flagged = _baseline_flagged(tmp_path, monkeypatch, target)

    monkeypatch.setenv("VAR_COMPLIANCE_WEBHOOK_URL", WEBHOOK_URL)
    calls = []
    _install_failing_urlopen(monkeypatch, kind, calls)

    result = secret_scanner.scan_files([target], repo_root=tmp_path)

    matches = field(result, "matches")
    assert any(field(m, "risk_tier") == "high" for m in matches), matches

    # The webhook call was attempted, at most once.
    assert len(calls) == 1

    assert field(result, "notified") is True

    error = field(result, "notification_delivery_error")
    assert error is not None
    assert field(error, "category") == expected_category
    message = field(error, "message")
    assert isinstance(message, str)

    flagged = field(result, "flagged")
    assert flagged is True
    assert flagged == bool(matches)
    assert flagged == baseline_flagged

    as_dict = result.to_dict()
    assert as_dict["notified"] is True
    assert as_dict["flagged"] is True
    assert as_dict["notification_delivery_error"]["category"] == expected_category