# hotdocs-criterion: sha256:262f8668dfd128d83b8aa4481dc4d74d09f01e6fa07fef14adfe4c8d9f85e2d9
import hashlib
import json
import os
import re
import socket
import sys
from pathlib import Path

import pytest

import license_scanner


COMPONENT_ID = "comp-foo"
COMPONENT_SLUG = "foo"


def _field(value, name):
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def _tokens(text):
    return [t.lower() for t in re.findall(r"[A-Za-z_][A-Za-z0-9_]*|\d+", text)]


def _window_hashes(text):
    toks = _tokens(text)
    out = []
    seen = set()
    for i in range(len(toks) - 8):
        joined = "\x1f".join(toks[i:i + 9])
        h = hashlib.sha256(joined.encode("utf-8")).hexdigest()
        if h not in seen:
            seen.add(h)
            out.append(h)
    return out


def _free_closed_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


FAKE_CACHE_MANAGER = '''
import json as _json


_LOG_PATH = {log_path!r}


def _log(record):
    try:
        with open(_LOG_PATH, "a", encoding="utf-8") as fh:
            fh.write(_json.dumps(record) + "\\n")
    except Exception:
        pass


class SchemaValidationError(ValueError):
    pass


class Miss:
    def __eq__(self, other):
        return isinstance(other, Miss)

    def __hash__(self):
        return hash("Miss")


class CacheKey:
    def __init__(self, spec_bundle_hash=None, gate_inputs_hash=None, gate_version=None, model_pin=None):
        self.spec_bundle_hash = spec_bundle_hash
        self.gate_inputs_hash = gate_inputs_hash
        self.gate_version = gate_version
        self.model_pin = model_pin


class CachedResult:
    def __init__(self, gate_type=None, payload=None, stored_at=None):
        self.gate_type = gate_type
        self.payload = payload
        self.stored_at = stored_at


def get(cache_key, *, repo_root=None):
    _log({{"call": "get"}})
    return Miss()


def put(cache_key, result, *, repo_root=None):
    _log({{"call": "put"}})
    return None


def now_iso():
    import datetime
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def stats(*, repo_root=None):
    return {{"entry_count": 0}}
'''


@pytest.fixture
def repo(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    # Fake cache-manager (always a miss) so every scan is fresh.
    cm_dir = repo_root / "gen" / "cache-manager"
    cm_dir.mkdir(parents=True)
    log_path = tmp_path / "cache_calls.log"
    (cm_dir / "cache_manager.py").write_text(
        FAKE_CACHE_MANAGER.format(log_path=str(log_path)), encoding="utf-8"
    )

    # Component source under gen/<slug>/.
    comp_dir = repo_root / "gen" / COMPONENT_SLUG
    comp_dir.mkdir(parents=True)
    lines = [
        "value_{i} = compute_{i}(item_{i}, {n})".format(i=i, n=i * 7 + 3)
        for i in range(40)
    ]
    source = "\n".join(lines) + "\n"
    (comp_dir / "foo.py").write_text(source, encoding="utf-8")

    hashes = _window_hashes(source)
    assert len(hashes) > 50
    # Roughly 90% overlap: a strong, reportable match, but below a 1.0
    # block threshold, so blocking is driven purely by confidence and the
    # notification is due purely because of the high risk_tier.
    keep = int(len(hashes) * 0.9)
    corpus = {
        "corpus_version": 3,
        "block_threshold": 1.0,
        "entries": [
            {
                "reference_id": "ref-high-001",
                "license_family": "GPL",
                "risk_tier": "high",
                "hashes": hashes[:keep],
            }
        ],
    }
    corpus_path = repo_root / "corpus.json"
    corpus_path.write_text(json.dumps(corpus), encoding="utf-8")

    monkeypatch.chdir(repo_root)
    monkeypatch.setenv("VAR_LICENSE_CORPUS_PATH", str(corpus_path))
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    return repo_root


def test_webhook_network_error_recorded_without_affecting_notified_or_blocked(repo, monkeypatch):
    # Baseline: same scan with no webhook configured.
    baseline = license_scanner.scan(COMPONENT_ID, repo)
    assert _field(baseline, "evaluated") is True
    baseline_blocked = _field(baseline, "blocked")
    assert isinstance(baseline_blocked, bool)
    assert _field(baseline, "notified") is False
    assert _field(baseline, "notification_delivery_error") is None

    baseline_matches = _field(baseline, "matches") or []
    assert any(_field(m, "risk_tier") == "high" for m in baseline_matches)

    # Now configure a webhook pointing at a closed local port: the call
    # itself fails with a network error (connection refused).
    port = _free_closed_port()
    monkeypatch.setenv("VAR_COMPLIANCE_WEBHOOK_URL", "http://127.0.0.1:%d/hook" % port)

    result = license_scanner.scan(COMPONENT_ID, repo)  # must not raise

    assert _field(result, "evaluated") is True
    matches = _field(result, "matches") or []
    assert any(_field(m, "risk_tier") == "high" for m in matches)

    # notified reflects that a notification was due, not delivery outcome.
    assert _field(result, "notified") is True

    err = _field(result, "notification_delivery_error")
    assert err is not None
    assert _field(err, "category") == "network"
    message = _field(err, "message")
    assert message is not None

    # blocked is unaffected by the delivery failure.
    blocked = _field(result, "blocked")
    assert blocked == baseline_blocked
    score = _field(result, "similarity_score")
    threshold = _field(result, "block_threshold")
    assert score is not None and threshold is not None
    assert blocked == (score >= threshold)
    assert blocked is False