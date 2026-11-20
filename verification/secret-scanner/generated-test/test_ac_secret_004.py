# hotdocs-criterion: sha256:40bc64e7a6511dc58e56b070adc14ca1eb45fa376a5d65018aa3bc678ac8cc19
import urllib.request

import pytest

import secret_scanner


WEBHOOK_URL = "http://127.0.0.1:9/compliance-hook"

# Built by concatenation so this test file itself holds no detectable key shape.
AWS_KEY_SHAPE = "AKIA" + "IOSFODNN" + "7EXAMPLE"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


class _FakeResponse:
    status = 200

    def getcode(self):
        return 200

    def read(self, *args, **kwargs):
        return b""

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _request_url(req):
    if isinstance(req, str):
        return req
    full = getattr(req, "full_url", None)
    if full is not None:
        return full
    get = getattr(req, "get_full_url", None)
    return get() if get is not None else req


@pytest.fixture
def recorder(monkeypatch):
    calls = []

    def fake_urlopen(req, *args, **kwargs):
        calls.append(_request_url(req))
        return _FakeResponse()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    if hasattr(secret_scanner, "urlopen"):
        monkeypatch.setattr(secret_scanner, "urlopen", fake_urlopen)
    return calls


@pytest.fixture
def repo_root(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _write_secret_file(repo_root):
    target = repo_root / "config.py"
    target.write_text("AWS_ACCESS_KEY_ID = " + repr(AWS_KEY_SHAPE) + "\n")
    return target


def _write_clean_file(repo_root):
    target = repo_root / "config.py"
    target.write_text("GREETING = " + repr("hello") + "\n")
    return target


def test_high_risk_match_sends_notification_even_if_later_scan_clean(
    repo_root, recorder, monkeypatch
):
    monkeypatch.setenv("VAR_COMPLIANCE_WEBHOOK_URL", WEBHOOK_URL)
    target = _write_secret_file(repo_root)

    first = secret_scanner.scan(repo_root)

    matches = field(first, "matches")
    assert any(field(m, "risk_tier") == "high" for m in matches), matches
    assert field(first, "flagged") is True
    assert field(first, "notified") is True
    assert len(recorder) == 1, recorder
    assert recorder[0] == WEBHOOK_URL

    # A later retry that scans clean never un-notifies the earlier one.
    _write_clean_file(repo_root)
    assert target.read_text().find("AKIA") == -1

    second = secret_scanner.scan(repo_root)
    assert field(second, "flagged") is False
    assert field(second, "notified") is False
    assert len(recorder) == 1, recorder
    assert recorder[0] == WEBHOOK_URL
    assert field(first, "notified") is True


def test_no_match_with_webhook_configured_does_not_notify(
    repo_root, recorder, monkeypatch
):
    monkeypatch.setenv("VAR_COMPLIANCE_WEBHOOK_URL", WEBHOOK_URL)
    _write_clean_file(repo_root)

    result = secret_scanner.scan(repo_root)

    assert field(result, "matches") == []
    assert field(result, "flagged") is False
    assert field(result, "notified") is False
    assert recorder == []


def test_high_risk_match_with_webhook_unset_flags_without_notifying(
    repo_root, recorder, monkeypatch
):
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)
    _write_secret_file(repo_root)

    result = secret_scanner.scan(repo_root)

    matches = field(result, "matches")
    assert any(field(m, "risk_tier") == "high" for m in matches), matches
    assert field(result, "flagged") is True
    assert field(result, "notified") is False
    assert recorder == []