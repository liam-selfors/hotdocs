import urllib.request
from pathlib import Path

import secret_scanner


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


AWS_EXAMPLE_KEY = "AKIAIOSFODNN7EXAMPLE"


class _DummyResponse:
    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def read(self):
        return b"{}"

    def getcode(self):
        return 200


def _make_recorder(calls):
    def _urlopen(*args, **kwargs):
        calls.append((args, kwargs))
        return _DummyResponse()

    return _urlopen


def _write_secret_file(repo_root: Path) -> None:
    target = repo_root / "src" / "config.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text('aws_access_key_id = "%s"\n' % AWS_EXAMPLE_KEY)


def _write_clean_file(repo_root: Path) -> None:
    target = repo_root / "src" / "config.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text('greeting = "hello world"\n')


def test_notification_sent_for_high_risk_match_survives_later_clean_retry(
    tmp_path, monkeypatch
):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write_secret_file(repo_root)

    monkeypatch.setenv("VAR_COMPLIANCE_WEBHOOK_URL", "https://example.invalid/hook")

    calls = []
    monkeypatch.setattr(urllib.request, "urlopen", _make_recorder(calls))

    result1 = secret_scanner.scan(repo_root)

    assert _get(result1, "flagged") is True
    matches1 = _get(result1, "matches")
    assert len(matches1) >= 1
    assert any(_get(m, "risk_tier") == "high" for m in matches1)
    assert _get(result1, "notified") is True
    assert len(calls) == 1

    # Fix the secret and re-run: the earlier flagged attempt's notification
    # record must not be erased or retroactively cancelled by the clean retry.
    _write_clean_file(repo_root)

    result2 = secret_scanner.scan(repo_root)

    assert _get(result2, "flagged") is False
    assert _get(result2, "notified") is False
    assert len(calls) == 1


def test_no_match_means_not_notified_and_webhook_never_called(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write_clean_file(repo_root)

    monkeypatch.setenv("VAR_COMPLIANCE_WEBHOOK_URL", "https://example.invalid/hook")

    calls = []
    monkeypatch.setattr(urllib.request, "urlopen", _make_recorder(calls))

    result = secret_scanner.scan(repo_root)

    assert _get(result, "flagged") is False
    assert _get(result, "notified") is False
    assert calls == []


def test_webhook_unset_means_flagged_but_never_notified(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write_secret_file(repo_root)

    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)

    calls = []
    monkeypatch.setattr(urllib.request, "urlopen", _make_recorder(calls))

    result = secret_scanner.scan(repo_root)

    assert _get(result, "flagged") is True
    matches = _get(result, "matches")
    assert len(matches) >= 1
    assert any(_get(m, "risk_tier") == "high" for m in matches)
    assert _get(result, "notified") is False
    assert calls == []