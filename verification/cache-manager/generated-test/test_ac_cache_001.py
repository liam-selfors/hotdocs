"""AC-CACHE-001 (Covers: R-CACHE-001).

Given no entry stored for a given cache key
When get is called with that key
Then it returns Miss, not an error and not a partial result
"""

import dataclasses

import pytest

import cache_manager


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _hash(ch):
    return "sha256:" + (ch * 64)


def _key(**overrides):
    values = dict(
        spec_bundle_hash=_hash("a"),
        gate_inputs_hash=_hash("b"),
        gate_version="license_scanner@4.0.3+9f2c41ab07de",
        model_pin="claude-sonnet-5",
    )
    values.update(overrides)
    return cache_manager.CacheKey(**values)


def _result():
    return cache_manager.CachedResult(
        gate_type="license_scanner",
        payload={
            "component_id": "comp-example",
            "gate_version": "license_scanner@4.0.3+9f2c41ab07de",
            "similarity_score": 0.0,
            "blocked": False,
            "matches": [],
        },
        stored_at=cache_manager.now_iso(),
    )


@pytest.fixture
def repo_root(tmp_path, monkeypatch):
    # Force the local fallback store, scoped to a fresh, empty repo root.
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    root = tmp_path / "repo"
    root.mkdir()
    monkeypatch.chdir(root)
    return root


def _assert_definitive_miss(result):
    assert result is not None, "get must report a miss as a Miss instance, never None"
    assert isinstance(result, cache_manager.Miss), (
        f"expected a Miss, got {type(result)!r}: {result!r}"
    )
    assert not isinstance(result, cache_manager.CachedResult)
    assert result == cache_manager.Miss()


def test_get_on_empty_store_returns_miss(repo_root):
    assert cache_manager.stats(repo_root=repo_root)["entry_count"] == 0

    result = cache_manager.get(_key(), repo_root=repo_root)

    _assert_definitive_miss(result)


def test_get_on_empty_store_default_repo_root_returns_miss(repo_root):
    # repo_root defaults to the current working directory (the fresh tmp root).
    result = cache_manager.get(_key())

    _assert_definitive_miss(result)


@pytest.mark.parametrize(
    "overrides",
    [
        {"spec_bundle_hash": _hash("c")},
        {"gate_inputs_hash": _hash("d")},
        {"gate_version": "license_scanner@4.0.4+9f2c41ab07de"},
        {"model_pin": "claude-sonnet-5-5"},
    ],
    ids=["spec_bundle_hash", "gate_inputs_hash", "gate_version", "model_pin"],
)
def test_get_for_unstored_near_key_returns_miss_not_approximate(repo_root, overrides):
    stored_key = _key()
    stored = _result()
    cache_manager.put(stored_key, stored, repo_root=repo_root)

    # Sanity: the exact key is a hit, so the store really holds a neighbour.
    hit = cache_manager.get(stored_key, repo_root=repo_root)
    assert not isinstance(hit, cache_manager.Miss)
    assert field(hit, "gate_type") == "license_scanner"
    assert field(hit, "payload") == stored.payload

    # A key differing in exactly one field has no entry: it must be a
    # definitive Miss, never the "probably equivalent" neighbour's result.
    unstored_key = dataclasses.replace(stored_key, **overrides)
    assert unstored_key != stored_key

    result = cache_manager.get(unstored_key, repo_root=repo_root)

    _assert_definitive_miss(result)