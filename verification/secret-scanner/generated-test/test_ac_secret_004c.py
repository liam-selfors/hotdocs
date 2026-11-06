import textwrap
import urllib.request

import secret_scanner


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def test_clean_scan_notified_false(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    (repo_root / "README.md").write_text(
        "This is a plain readme with no secrets in it.\n",
        encoding="utf-8",
    )
    (repo_root / "app.py").write_text(
        textwrap.dedent(
            """
            def greet(name):
                return "hello " + name
            """
        ),
        encoding="utf-8",
    )

    # Configure the webhook so a false "notified" result is proven to come
    # from the absence of any match, not from the webhook being unconfigured.
    monkeypatch.setenv("VAR_COMPLIANCE_WEBHOOK_URL", "https://example.invalid/webhook")

    call_log = tmp_path / "urlopen_calls.log"

    def fake_urlopen(*args, **kwargs):
        with open(call_log, "a", encoding="utf-8") as f:
            f.write("called\n")
        raise AssertionError("urlopen should not be called for a clean scan")

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    result = secret_scanner.scan(repo_root)

    assert _get(result, "matches") == []
    assert _get(result, "flagged") is False
    assert _get(result, "notified") is False
    assert not call_log.exists()