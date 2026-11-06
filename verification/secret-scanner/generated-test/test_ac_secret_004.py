import urllib.request

import secret_scanner


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


AWS_KEY_LINE = 'AWS_KEY = "AKIAIOSFODNN7EXAMPLE"\n'


def _write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


class _FakeResponse:
    status = 200
    code = 200

    def getcode(self):
        return 200

    def read(self):
        return b"{}"

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False


class _Recorder:
    def __init__(self):
        self.calls = []

    def __call__(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return _FakeResponse()


def test_notification_sent_for_high_risk_match_independent_of_later_clean_retry(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("VAR_COMPLIANCE_WEBHOOK_URL", "https://example.invalid/hook")
    recorder = _Recorder()
    monkeypatch.setattr(urllib.request, "urlopen", recorder)

    repo_root = tmp_path / "repo"
    secret_file = repo_root / "config.py"
    _write(secret_file, AWS_KEY_LINE)

    result1 = secret_scanner.scan_files([secret_file], repo_root=repo_root)

    assert _get(result1, "flagged") is True
    assert _get(result1, "notified") is True
    assert len(recorder.calls) == 1

    _write(secret_file, "# now clean, no secret here\n")
    result2 = secret_scanner.scan_files([secret_file], repo_root=repo_root)

    assert _get(result2, "flagged") is False
    assert _get(result2, "notified") is False
    assert len(recorder.calls) == 1
    assert _get(result1, "notified") is True


def test_no_match_at_all_means_no_notification_and_no_webhook_call(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("VAR_COMPLIANCE_WEBHOOK_URL", "https://example.invalid/hook")
    recorder = _Recorder()
    monkeypatch.setattr(urllib.request, "urlopen", recorder)

    repo_root = tmp_path / "repo"
    clean_file = repo_root / "clean.py"
    _write(clean_file, "x = 1\n")

    result = secret_scanner.scan_files([clean_file], repo_root=repo_root)

    assert _get(result, "flagged") is False
    assert _get(result, "notified") is False
    assert recorder.calls == []


def test_webhook_unset_means_flagged_true_but_not_notified_and_no_webhook_call(
    tmp_path, monkeypatch
):
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)
    recorder = _Recorder()
    monkeypatch.setattr(urllib.request, "urlopen", recorder)

    repo_root = tmp_path / "repo"
    secret_file = repo_root / "config.py"
    _write(secret_file, AWS_KEY_LINE)

    result = secret_scanner.scan_files([secret_file], repo_root=repo_root)

    assert _get(result, "flagged") is True
    assert _get(result, "notified") is False
    assert recorder.calls == []