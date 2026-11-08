import hashlib
import json

import license_scanner


def _field(obj, name):
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


def _window_hash(tokens):
    joined = "\x1f".join(tokens)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


CACHE_MANAGER_SOURCE = '''
from dataclasses import dataclass
from typing import Any


@dataclass
class CacheKey:
    spec_bundle_hash: str
    gate_inputs_hash: str
    gate_version: str
    model_pin: str


@dataclass
class CachedResult:
    gate_type: str
    payload: Any
    stored_at: str


class _Miss:
    payload = None


def get(cache_key, *, repo_root=None):
    return _Miss()


def put(cache_key, result, *, repo_root=None):
    return None
'''


def test_blocked_low_risk_tier_no_webhook_still_records_result(tmp_path, monkeypatch):
    repo_root = tmp_path

    cache_manager_dir = repo_root / "gen" / "cache-manager"
    cache_manager_dir.mkdir(parents=True)
    (cache_manager_dir / "cache_manager.py").write_text(CACHE_MANAGER_SOURCE, encoding="utf-8")

    tokens = ["alpha", "bravo", "charlie", "delta", "echo", "foxtrot", "golf", "hotel", "india"]
    matching_hash = _window_hash(tokens)

    scanned_component_dir = repo_root / "gen" / "sample-widget"
    scanned_component_dir.mkdir(parents=True)
    (scanned_component_dir / "main.py").write_text(" ".join(tokens) + "\n", encoding="utf-8")

    corpus = {
        "corpus_version": 1,
        "block_threshold": 0.70,
        "entries": [
            {
                "reference_id": "ref-low-1",
                "license_family": "mit",
                "risk_tier": "low",
                "hashes": [matching_hash],
            }
        ],
    }
    corpus_path = repo_root / "reference-corpus.json"
    corpus_path.write_text(json.dumps(corpus), encoding="utf-8")

    monkeypatch.setenv("VAR_LICENSE_CORPUS_PATH", str(corpus_path))
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)

    result = license_scanner.scan("comp-sample-widget", repo_root)

    assert _field(result, "evaluated") is True
    assert _field(result, "blocked") is True
    assert _field(result, "notified") is False
    assert _field(result, "notification_delivery_error") is None

    similarity_score = _field(result, "similarity_score")
    block_threshold = _field(result, "block_threshold")
    assert similarity_score is not None
    assert block_threshold is not None
    assert similarity_score >= block_threshold

    matches = _field(result, "matches")
    assert matches
    found_low_match = False
    for match in matches:
        if _field(match, "reference_id") == "ref-low-1":
            assert _field(match, "risk_tier") == "low"
            found_low_match = True
    assert found_low_match

    assert _field(result, "component_id") == "comp-sample-widget"
    assert _field(result, "gate_version") is not None