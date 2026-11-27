# hotdocs-criterion: sha256:86ff2b1991ee1cc1554ba54a302ad6969dcdcbc319b4b6ab6c3a0b063d637557
"""AC-SECRET-011: a failing compliance webhook call is caught and recorded.

Covers R-SECRET-004: when a high-risk match is found and
VAR-COMPLIANCE-WEBHOOK-URL is configured, the webhook call is attempted at
most once. Any failure is caught and recorded as notification_delivery_error
with category "network", "auth" (HTTP 401/403) or "timeout". It is never
raised and never affects `flagged`.
"""

import socket
import urllib.error
import urllib.request
from pathlib import Path

import pytest

import secret_scanner


WEBHOOK_URL = "http://compliance.example.invalid/hook"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


# A flat-module fake of cache-manager that always misses. It matches the
# documented names and signatures: CacheKey, CachedResult, Miss, get, put,
# now_iso, stats, SchemaValidationError. It embeds no random-looking literal.
FAKE_CACHE_MANAGER_SOURCE = (
    "from dataclasses import dataclass\n"
    "from datetime import datetime, timezone\n"
    "\n"
    "\n"
    "@dataclass\n"
    "class CacheKey:\n"
    "    spec_bundle_hash: str\n"
    "    gate_inputs_hash: str\n"
    "    gate_version: str\n"
    "    model_pin: str\n"
    "\n"
    "\n"
    "@dataclass\n"
    "class CachedResult:\n"
    "    gate_type: str\n"
    "    payload: dict\n"
    "    stored_at: str\n"
    "\n"
    "\n"
    "class Miss:\n"
    "    def __eq__(self, other):\n"
    "        return isinstance(other, Miss)\n"
    "\n"
    "    def __hash__(self):\n"
    "        return 0\n"
    "\n"
    "\n"
    "class SchemaValidationError(ValueError):\n"
    "    pass\n"
    "\n"
    "\n"
    "_REQUIRED = " + repr({
        "secret_scanner": ["scope", "gate_version", "flagged", "matches"],
    }) + "\n"
    "\n"
    "\n"
    "def get(cache_key, *, repo_root=None):\n"
    "    return Miss()\n"
    "\n"
    "\n"
    "def put(cache_key, result, *, repo_root=None):\n"
    "    payload = result.payload if not isinstance(result, dict) else result.get('payload')\n"
    "    gate_type = result.gate_type if not isinstance(result, dict) else result.get('gate_type')\n"
    "    for key in _REQUIRED.get(gate_type, []):\n"
    "        if not isinstance(payload, dict) or key not in payload:\n"
    "            raise SchemaValidationError('missing payload key: ' + str(key))\n"
    "    return None\n"
    "\n"
    "\n"
    "def now_iso():\n"
    "    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')\n"
    "\n"
    "\n"
    "def stats(*, repo_root=None):\n"
    "    return " + repr({"entry_count": 0}) + "\n"
)


def _build_repo(repo_root: Path) -> None:
    fake_dir = repo_root / "gen" / "cache-manager"
    fake_dir.mkdir(parents=True)
    (fake_dir / "cache_manager.py").write_text(FAKE_CACHE_MANAGER_SOURCE)

    # Build the planted AWS key by concatenation so this test file itself
    # carries no detectable secret literal.
    planted = "AKIA" + "IOSFODNN7" + "EXAMPLE"
    target_dir = repo_root / "gen" / "foo"
    target_dir.mkdir(parents=True)
    (target_dir / "config.py").write_text(
        "AWS_ACCESS_KEY_ID = " + repr(planted) + "\n"
    )


def _http_error(code):
    return urllib.error.HTTPError(WEBHOOK_URL, code, "error", {}, None)


CASES = [
    ("network-error", lambda: urllib.error.URLError("connection refused"), "network"),
    ("http-401", lambda: _http_error(401), "auth"),
    ("socket-timeout", lambda: socket.timeout("timed out"), "timeout"),
    ("http-500", lambda: _http_error(500), "network"),
]


@pytest.mark.parametrize(
    "make_exc,expected_category",
    [(c[1], c[2]) for c in CASES],
    ids=[c[0] for c in CASES],
)
def test_webhook_failure_is_recorded_not_raised(
    tmp_path, monkeypatch, make_exc, expected_category
):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_repo(repo_root)

    monkeypatch.setenv("VAR_COMPLIANCE_WEBHOOK_URL", WEBHOOK_URL)
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)

    calls = []

    def failing_urlopen(*args, **kwargs):
        calls.append((args, kwargs))
        raise make_exc()

    monkeypatch.setattr(urllib.request, "urlopen", failing_urlopen)
    if hasattr(secret_scanner, "urlopen"):
        monkeypatch.setattr(secret_scanner, "urlopen", failing_urlopen)

    # Must not raise despite the webhook failure.
    result = secret_scanner.scan(repo_root)

    matches = field(result, "matches")
    high = [m for m in matches if field(m, "risk_tier") == "high"]
    assert high, "precondition: expected a high-risk match, got " + repr(matches)

    # The webhook was attempted, and at most once.
    assert len(calls) == 1, "expected exactly one webhook attempt, got " + repr(len(calls))

    assert field(result, "notified") is True

    error = field(result, "notification_delivery_error")
    assert error is not None
    assert field(error, "category") == expected_category

    # flagged is unaffected by the delivery failure: it is true iff matches is non-empty.
    assert field(result, "flagged") is True
    assert field(result, "flagged") == bool(matches)

    as_dict = result.to_dict()
    assert as_dict["notified"] is True
    assert as_dict["flagged"] is True
    assert field(as_dict["notification_delivery_error"], "category") == expected_category