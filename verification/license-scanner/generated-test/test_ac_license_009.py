import hashlib
import json
import socket

import license_scanner


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _window_hash(tokens):
    return hashlib.sha256("\x1f".join(tokens).encode("utf-8")).hexdigest()


def _unused_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


_CACHE_MANAGER_SOURCE = """
from dataclasses import dataclass


@dataclass
class CacheKey:
    spec_bundle_hash: str
    gate_inputs_hash: str
    gate_version: str
    model_pin: str


@dataclass
class CachedResult:
    gate_type: str
    payload: object
    stored_at: str


def get(cache_key, *, repo_root=None):
    return {"payload": None}


def put(cache_key, result, *, repo_root=None):
    pass
"""


def test_ac_license_009(tmp_path, monkeypatch):
    repo_root = tmp_path

    cache_manager_dir = repo_root / "gen" / "cache-manager"
    cache_manager_dir.mkdir(parents=True)
    (cache_manager_dir / "cache_manager.py").write_text(_CACHE_MANAGER_SOURCE)

    scanned_slug = "target-app"
    scanned_dir = repo_root / "gen" / scanned_slug
    scanned_dir.mkdir(parents=True)

    source_tokens = [
        "foo", "bar", "baz", "qux", "quux",
        "corge", "grault", "garply", "waldo",
    ]
    (scanned_dir / "app.py").write_text("\n".join(source_tokens) + "\n")

    entry_hash = _window_hash(source_tokens)

    corpus = {
        "corpus_version": 1,
        "block_threshold": 0.70,
        "entries": [
            {
                "reference_id": "ref-001",
                "license_family": "GPL",
                "risk_tier": "high",
                "hashes": [entry_hash],
            }
        ],
    }
    (repo_root / "corpus.json").write_text(json.dumps(corpus))

    monkeypatch.setenv("VAR_LICENSE_CORPUS_PATH", "corpus.json")

    unreachable_port = _unused_port()
    monkeypatch.setenv(
        "VAR_COMPLIANCE_WEBHOOK_URL",
        "http://127.0.0.1:%d/webhook" % unreachable_port,
    )

    result = license_scanner.scan("comp-target-app", repo_root)

    similarity_score = _get(result, "similarity_score")
    block_threshold = _get(result, "block_threshold")
    blocked = _get(result, "blocked")
    notified = _get(result, "notified")
    delivery_error = _get(result, "notification_delivery_error")
    matches = _get(result, "matches")

    assert similarity_score == 1.0
    assert block_threshold == 0.70

    found_high_risk_match = any(
        _get(match, "reference_id") == "ref-001"
        and _get(match, "risk_tier") == "high"
        for match in matches
    )
    assert found_high_risk_match

    assert notified is True

    assert delivery_error is not None
    assert _get(delivery_error, "category") == "network"
    message = _get(delivery_error, "message")
    assert isinstance(message, str) and message

    # blocked reflects confidence only; a failed webhook call must not alter it.
    assert blocked is True