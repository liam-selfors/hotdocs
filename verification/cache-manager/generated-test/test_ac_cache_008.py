import os
import shutil
import tempfile
from pathlib import Path

import cache_manager


def _field(obj, name):
    return obj.get(name) if isinstance(obj, dict) else getattr(obj, name, None)


def _make_key(tag):
    return cache_manager.CacheKey(
        spec_bundle_hash=f"sha256:{tag}-bundle",
        gate_inputs_hash=f"sha256:{tag}-inputs",
        gate_version="license_scanner@1.0.0",
        model_pin="claude-sonnet-5",
    )


def _make_result():
    return cache_manager.CachedResult(
        gate_type="license_scanner",
        payload={
            "component_id": "comp-fake-under-test",
            "gate_version": "license_scanner@1.0.0",
            "similarity_score": 0.0,
            "blocked": False,
            "matches": [],
        },
        stored_at=cache_manager.now_iso(),
    )


def test_evicted_key_miss_matches_error_and_never_stored_miss():
    original_store_url = os.environ.pop("VAR_CACHE_STORE_URL", None)
    tmp_evicted = tempfile.mkdtemp()
    tmp_never_stored = tempfile.mkdtemp()
    try:
        evicted_repo_root = Path(tmp_evicted)
        key_evicted = _make_key("evicted")
        cache_manager.put(key_evicted, _make_result(), repo_root=evicted_repo_root)

        hit_before_eviction = cache_manager.get(key_evicted, repo_root=evicted_repo_root)
        assert not isinstance(hit_before_eviction, cache_manager.Miss)

        stats_before = cache_manager.stats(repo_root=evicted_repo_root)
        assert _field(stats_before, "entry_count") >= 1

        # Simulate the backing store evicting the entry on its own, with no
        # coordination: wipe the local-fallback store out from under the key
        # that was already successfully put.
        cache_dir = evicted_repo_root / ".hotdocs" / "cache"
        assert cache_dir.exists()
        shutil.rmtree(cache_dir)

        stats_after = cache_manager.stats(repo_root=evicted_repo_root)
        assert _field(stats_after, "entry_count") == 0

        miss_evicted = cache_manager.get(key_evicted, repo_root=evicted_repo_root)

        # A backing-store error (R-CACHE-004) is documented to degrade to the
        # same definitive-miss shape, never an exception.
        os.environ["VAR_CACHE_STORE_URL"] = "not-a-real-scheme://unreachable.invalid:1/nowhere"
        try:
            key_error = _make_key("error")
            miss_error = cache_manager.get(key_error, repo_root=evicted_repo_root)
        finally:
            os.environ.pop("VAR_CACHE_STORE_URL", None)

        never_stored_repo_root = Path(tmp_never_stored)
        key_never_stored = _make_key("never-stored")
        miss_never_stored = cache_manager.get(key_never_stored, repo_root=never_stored_repo_root)

        assert isinstance(miss_evicted, cache_manager.Miss)
        assert isinstance(miss_error, cache_manager.Miss)
        assert isinstance(miss_never_stored, cache_manager.Miss)

        assert type(miss_evicted) is type(miss_error) is type(miss_never_stored)

        assert miss_evicted == miss_never_stored
        assert miss_evicted == miss_error
        assert miss_error == miss_never_stored
    finally:
        os.environ.pop("VAR_CACHE_STORE_URL", None)
        if original_store_url is not None:
            os.environ["VAR_CACHE_STORE_URL"] = original_store_url
        shutil.rmtree(tmp_evicted, ignore_errors=True)
        shutil.rmtree(tmp_never_stored, ignore_errors=True)