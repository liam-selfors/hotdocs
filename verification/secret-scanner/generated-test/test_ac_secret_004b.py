import shutil
import tempfile
import urllib.request
from pathlib import Path

import secret_scanner


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


class _FakeWebhookResponse:
    status = 200

    def read(self):
        return b"OK"

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False


def test_ac_secret_004b_low_tier_blocking_match_still_notifies(monkeypatch):
    repo_root = Path(tempfile.mkdtemp(prefix="hotdocs-ac-secret-004b-"))
    try:
        foo_dir = repo_root / "gen" / "foo"
        foo_dir.mkdir(parents=True)
        (foo_dir / "h.py").write_text(
            'sha = "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b"\n'
        )

        monkeypatch.setenv(
            "VAR_COMPLIANCE_WEBHOOK_URL", "https://example.invalid/webhook"
        )

        calls = []

        def fake_urlopen(*args, **kwargs):
            calls.append((args, kwargs))
            return _FakeWebhookResponse()

        monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

        result = secret_scanner.scan(repo_root)

        assert _get(result, "flagged") is True

        matches = _get(result, "matches") or []
        target_matches = [
            m
            for m in matches
            if str(_get(m, "file", "")).replace("\\", "/") == "gen/foo/h.py"
        ]
        assert target_matches, (
            "expected at least one match for gen/foo/h.py, got matches=%r" % matches
        )
        assert all(_get(m, "risk_tier") == "low" for m in target_matches)

        assert len(calls) == 1
    finally:
        shutil.rmtree(repo_root, ignore_errors=True)