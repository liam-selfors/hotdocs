import email.message
import json
import os
import socket
import urllib.error
import urllib.request
from pathlib import Path

import pytest

import secret_scanner


WEBHOOK_URL = "http://compliance-hook.invalid/notify"
CACHE_LOG_ENV = "AC011_FAKE_CACHE_LOG"


FAKE_CACHE_MANAGER_SOURCE = '''
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone


_REQUIRED_PAYLOAD_KEYS = {
    "generator": ["component_id", "model", "prompt_version", "files"],
    "compiler": ["outputs", "gate_version", "summary"],
    "generated_test": ["component_id", "criterion_id", "model", "file"],
    "llm_judge": ["result", "rationale"],
    "license_scanner": ["component_id", "gate_version", "similarity_score", "blocked", "matches"],
    "secret_scanner": ["scope", "gate_version", "flagged", "matches"],
}


def _log(event):
    log_path = os.environ.get("AC011_FAKE_CACHE_LOG")
    if log_path:
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"event": event}) + "\\n")


@dataclass
class CacheKey:
    spec_bundle_hash: str
    gate_inputs_hash: str
    gate_version: str
    model_pin: str


@dataclass
class CachedResult:
    gate_type: str
    payload: dict
    stored_at: str


class Miss:
    def __eq__(self, other):
        return isinstance(other, Miss)

    def __hash__(self):
        return 0


class SchemaValidationError(ValueError):
    pass


def get(cache_key, *, repo_root=None):
    _log("get")
    return Miss()


def put(cache_key, result, *, repo_root=None):
    _log("put")
    gate_type = result.get("gate_type") if isinstance(result, dict) else getattr(result, "gate_type", None)
    payload = result.get("payload") if isinstance(result, dict) else getattr(result, "payload", None)
    key_version = cache_key.get("gate_version") if isinstance(cache_key, dict) else getattr(cache_key, "gate_version", "")
    key_type = str(key_version or "").split("@", 1)[0]
    if gate_type not in _REQUIRED_PAYLOAD_KEYS or gate_type != key_type:
        raise SchemaValidationError("gate type mismatch")
    if not isinstance(payload, dict):
        raise SchemaValidationError("payload is not a mapping")
    for k in _REQUIRED_PAYLOAD_KEYS[gate_type]:
        if k not in payload:
            raise SchemaValidationError("missing payload key")
    return None


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def stats(*, repo_root=None):
    return {"entry_count": 0}
'''


def _get(value, name, default=None):
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _planted_key():
    # Built at runtime so this test file itself carries no detectable key.
    return "AKIA" + "QX7RZ4MB" + "2KLP9TWN"


def _make_repo(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    cm_dir = root / "gen" / "cache-manager"
    cm_dir.mkdir(parents=True, exist_ok=True)
    (cm_dir / "cache_manager.py").write_text(FAKE_CACHE_MANAGER_SOURCE, encoding="utf-8")
    target = root / "gen" / "foo"
    target.mkdir(parents=True, exist_ok=True)
    (target / "config.py").write_text(
        'AWS_ACCESS_KEY_ID = "' + _planted_key() + '"\n', encoding="utf-8"
    )
    return root


class _OkResponse:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self, *args, **kwargs):
        return b""

    def getcode(self):
        return 200

    def close(self):
        pass


def _run_scan(tmp_path, monkeypatch, name, raiser):
    repo_root = _make_repo(tmp_path / name)
    monkeypatch.setenv(CACHE_LOG_ENV, str(tmp_path / (name + "-cache.log")))
    monkeypatch.setenv("VAR_COMPLIANCE_WEBHOOK_URL", WEBHOOK_URL)
    calls = []

    def fake_urlopen(*args, **kwargs):
        calls.append({"args": args, "kwargs": kwargs})
        if raiser is None:
            return _OkResponse()
        raise raiser()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    result = secret_scanner.scan(repo_root)
    return result, calls


def _http_error(code, msg):
    def make():
        return urllib.error.HTTPError(WEBHOOK_URL, code, msg, email.message.Message(), None)
    return make


def _assert_high_match(result):
    matches = _get(result, "matches") or []
    tiers = [_get(m, "risk_tier") for m in matches]
    assert "high" in tiers, "precondition: expected a high risk_tier match, got %r" % (matches,)


def test_network_error_recorded_and_flagged_unaffected(tmp_path, monkeypatch):
    baseline, baseline_calls = _run_scan(tmp_path, monkeypatch, "baseline", None)
    _assert_high_match(baseline)
    assert _get(baseline, "notified") is True
    assert _get(baseline, "notification_delivery_error") is None
    assert len(baseline_calls) == 1

    def network_error():
        return urllib.error.URLError("connection refused")

    result, calls = _run_scan(tmp_path, monkeypatch, "network", network_error)
    _assert_high_match(result)

    assert len(calls) == 1, "webhook must be attempted exactly once, got %d" % len(calls)
    assert _get(result, "notified") is True

    err = _get(result, "notification_delivery_error")
    assert err is not None
    assert _get(err, "category") == "network"
    message = _get(err, "message")
    assert isinstance(message, str)

    matches = _get(result, "matches") or []
    flagged = _get(result, "flagged")
    assert flagged is bool(matches)
    assert flagged == _get(baseline, "flagged")
    assert matches == (_get(baseline, "matches") or [])


@pytest.mark.parametrize(
    "name,raiser,expected",
    [
        ("auth401", _http_error(401, "Unauthorized"), "auth"),
        ("timeout", lambda: socket.timeout("timed out"), "timeout"),
        ("http500", _http_error(500, "Internal Server Error"), "network"),
    ],
)
def test_delivery_error_category(tmp_path, monkeypatch, name, raiser, expected):
    result, calls = _run_scan(tmp_path, monkeypatch, name, raiser)
    _assert_high_match(result)

    assert len(calls) == 1, "webhook must be attempted exactly once, got %d" % len(calls)
    assert _get(result, "notified") is True

    err = _get(result, "notification_delivery_error")
    assert err is not None
    assert _get(err, "category") == expected

    matches = _get(result, "matches") or []
    assert _get(result, "flagged") is bool(matches)