# hotdocs-criterion: sha256:28cde41224bc6b12e3e3d501d92f7e120dc98f51bc4a0b5d642bcb35d1beab89
"""AC-CACHE-008: an entry evicted by the backing store after a successful put
reads back as a plain, definitive miss, identical in shape to a
backing-store error (R-CACHE-004) and to a key that was never stored."""

import shutil
from pathlib import Path

import cache_manager


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def make_key(suffix):
    return cache_manager.CacheKey(
        spec_bundle_hash="sha256:" + ("a" * 63) + suffix,
        gate_inputs_hash="sha256:" + ("b" * 63) + suffix,
        gate_version="license_scanner@4.0.3+9f2c41ab07de",
        model_pin="claude-sonnet-5",
    )


def make_result():
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


def evict_everything(repo_root):
    """Simulate the backing store evicting every entry, without notice."""
    cache_dir = Path(repo_root) / ".hotdocs" / "cache"
    if cache_dir.exists():
        shutil.rmtree(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)


def test_evicted_entry_is_a_plain_miss_identical_to_error_and_never_stored(
    tmp_path, monkeypatch
):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(tmp_path)

    # Local store in use: no remote backing store configured.
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)

    evicted_key = make_key("1")
    never_stored_key = make_key("2")

    # Given: a key that was successfully put (put returns None, no raise) ...
    assert cache_manager.put(evicted_key, make_result(), repo_root=repo_root) is None

    # ... then evicted by the backing store before any get for it.
    evict_everything(repo_root)

    # When: get is called with that key.
    evicted_result = cache_manager.get(evicted_key, repo_root=repo_root)

    # A key that was simply never stored.
    never_stored_result = cache_manager.get(never_stored_key, repo_root=repo_root)

    # A backing-store error: point the store at an unreachable endpoint.
    monkeypatch.setenv("VAR_CACHE_STORE_URL", "http://127.0.0.1:9/hotdocs-cache-unreachable")
    error_result = cache_manager.get(evicted_key, repo_root=repo_root)
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)

    # Then: a definitive miss in every case, never None, never a hit.
    for result in (evicted_result, never_stored_result, error_result):
        assert result is not None
        assert isinstance(result, cache_manager.Miss)
        assert not isinstance(result, cache_manager.CachedResult)

    # Indistinguishable in shape: same type, and all compare equal, so the
    # caller's handling is identical in all three cases.
    assert type(evicted_result) is type(never_stored_result) is type(error_result)
    assert evicted_result == never_stored_result
    assert evicted_result == error_result
    assert never_stored_result == error_result
    assert evicted_result == cache_manager.Miss()

    # A caller's single, uniform handling path yields the same outcome.
    def handle(result):
        if isinstance(result, cache_manager.Miss):
            return "recompute"
        return field(result, "payload")

    assert handle(evicted_result) == handle(never_stored_result) == handle(error_result) == "recompute"