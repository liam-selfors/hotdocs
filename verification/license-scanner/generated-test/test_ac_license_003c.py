import hashlib
import json
from pathlib import Path

import pytest

import license_scanner


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


_FAKE_CACHE_MANAGER_SOURCE = '''
import dataclasses
import json
import os


@dataclasses.dataclass
class CacheKey:
    spec_bundle_hash: str
    gate_inputs_hash: str
    gate_version: str
    model_pin: str


@dataclasses.dataclass
class CachedResult:
    gate_type: str
    payload: object
    stored_at: str


def get(cache_key, *, repo_root=None):
    return CachedResult(gate_type="license_scanner", payload=None, stored_at="1970-01-01T00:00:00Z")


def put(cache_key, result, *, repo_root=None):
    log_path = os.environ.get("FAKE_CACHE_LOG_PATH")
    if not log_path:
        return
    payload = result.get("payload") if isinstance(result, dict) else getattr(result, "payload", None)
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(payload) + "\\n")
'''


def test_block_without_webhook_notifies_false_but_still_records(tmp_path, monkeypatch):
    repo_root = tmp_path

    cache_manager_dir = repo_root / "gen" / "cache-manager"
    cache_manager_dir.mkdir(parents=True)
    (cache_manager_dir / "cache_manager.py").write_text(_FAKE_CACHE_MANAGER_SOURCE, encoding="utf-8")

    target_slug_dir = repo_root / "gen" / "fixture-target"
    target_slug_dir.mkdir(parents=True)
    source_text = "aaa = bbb + ccc + ddd + eee + fff + ggg + hhh + iii\n"
    (target_slug_dir / "fixture_target.py").write_text(source_text, encoding="utf-8")

    tokens = ["aaa", "bbb", "ccc", "ddd", "eee", "fff", "ggg", "hhh", "iii"]
    window_hash = hashlib.sha256("\x1f".join(tokens).encode("utf-8")).hexdigest()

    corpus = {
        "corpus_version": 1,
        "block_threshold": 0.70,
        "entries": [
            {
                "reference_id": "ref-100",
                "license_family": "MIT",
                "risk_tier": "low",
                "hashes": [window_hash],
            }
        ],
    }
    corpus_path = repo_root / "license_corpus.json"
    corpus_path.write_text(json.dumps(corpus), encoding="utf-8")

    log_path = repo_root / "cache_put_log.jsonl"

    monkeypatch.setenv("VAR_LICENSE_CORPUS_PATH", str(corpus_path))
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)
    monkeypatch.setenv("FAKE_CACHE_LOG_PATH", str(log_path))

    result = license_scanner.scan("comp-fixture-target", repo_root)

    similarity_score = _get(result, "similarity_score")
    block_threshold = _get(result, "block_threshold")
    assert similarity_score is not None and block_threshold is not None
    assert similarity_score >= block_threshold

    assert _get(result, "blocked") is True
    assert _get(result, "notified") is False
    assert _get(result, "notification_delivery_error") is None

    matches = _get(result, "matches") or []
    assert len(matches) > 0
    risk_tiers = {_get(m, "risk_tier") for m in matches}
    assert "low" in risk_tiers
    assert "high" not in risk_tiers

    assert log_path.exists(), "cache-manager.put was never invoked; LicenseScanResult was not recorded"
    recorded_lines = [line for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(recorded_lines) >= 1

    recorded_payload = json.loads(recorded_lines[-1])
    assert _get(recorded_payload, "component_id") == "comp-fixture-target"
    assert _get(recorded_payload, "blocked") is True
    recorded_matches = _get(recorded_payload, "matches") or []
    assert len(recorded_matches) > 0
    assert any(_get(m, "risk_tier") == "low" for m in recorded_matches)