import os
import sys
from pathlib import Path

import pytest

import cache_manager


def _field(value, name):
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


SPEC_BUNDLE_HASH = "sha256:" + "a" * 64
GATE_INPUTS_HASH = "sha256:" + "b" * 64
MODEL_PIN = "claude-sonnet-5"
OLD_GATE_VERSION = "license_scanner@1.0.0"
NEW_GATE_VERSION = "license_scanner@2.0.0"


def _key(gate_version):
    return cache_manager.CacheKey(
        spec_bundle_hash=SPEC_BUNDLE_HASH,
        gate_inputs_hash=GATE_INPUTS_HASH,
        gate_version=gate_version,
        model_pin=MODEL_PIN,
    )


def _result(gate_version, marker):
    return cache_manager.CachedResult(
        gate_type="license_scanner",
        payload={
            "component_id": "comp-example",
            "gate_version": gate_version,
            "similarity_score": 0.0,
            "blocked": False,
            "matches": [],
            "marker": marker,
        },
        stored_at=cache_manager.now_iso(),
    )


@pytest.fixture
def repo_root(tmp_path, monkeypatch):
    # Force the local fallback store under a fresh, isolated repo root.
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    root = tmp_path / "repo"
    root.mkdir()
    monkeypatch.chdir(root)
    return root


def test_get_with_different_gate_version_returns_miss(repo_root):
    old_key = _key(OLD_GATE_VERSION)
    cache_manager.put(old_key, _result(OLD_GATE_VERSION, "old"), repo_root=repo_root)

    # Sanity: the entry is actually retrievable under its own gate_version,
    # so the miss below is not merely a store that never hits.
    old_hit = cache_manager.get(old_key, repo_root=repo_root)
    assert not isinstance(old_hit, cache_manager.Miss), (
        "entry stored under the old gate_version should be a hit for that same key"
    )
    old_payload = _field(old_hit, "payload")
    assert _field(old_payload, "marker") == "old"

    new_key = _key(NEW_GATE_VERSION)
    result = cache_manager.get(new_key, repo_root=repo_root)

    assert result is not None
    assert isinstance(result, cache_manager.Miss), (
        "get under gate_version license_scanner@2.0.0 must return Miss, "
        "not the entry stored under license_scanner@1.0.0; got %r" % (result,)
    )


def test_entries_under_different_gate_versions_are_distinct_keys(repo_root):
    old_key = _key(OLD_GATE_VERSION)
    new_key = _key(NEW_GATE_VERSION)

    cache_manager.put(old_key, _result(OLD_GATE_VERSION, "old"), repo_root=repo_root)
    cache_manager.put(new_key, _result(NEW_GATE_VERSION, "new"), repo_root=repo_root)

    old_hit = cache_manager.get(old_key, repo_root=repo_root)
    new_hit = cache_manager.get(new_key, repo_root=repo_root)

    assert not isinstance(old_hit, cache_manager.Miss)
    assert not isinstance(new_hit, cache_manager.Miss)

    old_payload = _field(old_hit, "payload")
    new_payload = _field(new_hit, "payload")

    assert _field(old_payload, "marker") == "old"
    assert _field(old_payload, "gate_version") == OLD_GATE_VERSION
    assert _field(new_payload, "marker") == "new"
    assert _field(new_payload, "gate_version") == NEW_GATE_VERSION

    # Writing under the new gate_version must not have overwritten the old entry.
    stats = cache_manager.stats(repo_root=repo_root)
    assert _field(stats, "entry_count") == 2