# hotdocs-criterion: sha256:580fb6dd7b1328c770a23892793bf305761375c9eb9c45fd77e589bb8c193de4
"""AC-CACHE-008 / R-CACHE-008: an entry evicted by the backing store after a
successful put, before any get, yields a definitive miss indistinguishable in
shape from a backing-store error miss (R-CACHE-004) or a never-stored miss."""

import json
import shutil
from pathlib import Path

import cache_manager


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _key(suffix):
    return cache_manager.CacheKey(
        spec_bundle_hash="sha256:" + ("a" * 63) + suffix,
        gate_inputs_hash="sha256:" + ("b" * 63) + suffix,
        gate_version="license_scanner@4.0.3+9f2c41ab07de",
        model_pin="claude-sonnet-5",
    )


def _result():
    return cache_manager.CachedResult(
        gate_type="license_scanner",
        payload={
            "component_id": "comp-foo",
            "gate_version": "license_scanner@4.0.3+9f2c41ab07de",
            "similarity_score": 0.0,
            "blocked": False,
            "matches": [],
        },
        stored_at=cache_manager.now_iso(),
    )


def _inspect(key, repo_root, capsys):
    capsys.readouterr()
    code = cache_manager.main(
        [
            "inspect",
            "--spec-bundle-hash=" + key.spec_bundle_hash,
            "--gate-inputs-hash=" + key.gate_inputs_hash,
            "--gate-version=" + key.gate_version,
            "--model-pin=" + key.model_pin,
            "--repo-root=" + str(repo_root),
        ]
    )
    out = capsys.readouterr().out.strip().splitlines()
    return code, out


def test_evicted_entry_is_plain_miss_like_error_and_never_stored(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)

    # --- Case 1: put, then evicted by the backing store, before any get ---
    evict_root = tmp_path / "evict_repo"
    evict_root.mkdir()
    monkeypatch.chdir(evict_root)
    evicted_key = _key("1")
    cache_manager.put(evicted_key, _result(), repo_root=evict_root)

    cache_dir = evict_root / ".hotdocs" / "cache"
    assert cache_dir.exists(), "local fallback store should hold the put entry"
    stats_before = cache_manager.stats(repo_root=evict_root)
    assert field(stats_before, "entry_count") >= 1

    # Simulate the backing store evicting every entry, without notifying anyone.
    if cache_dir.is_dir():
        shutil.rmtree(cache_dir)
    else:
        cache_dir.unlink()
    cache_dir.mkdir(parents=True)

    evicted = cache_manager.get(evicted_key, repo_root=evict_root)

    # --- Case 2: key never stored ---
    never_root = tmp_path / "never_repo"
    never_root.mkdir()
    never_stored = cache_manager.get(_key("2"), repo_root=never_root)

    # --- Case 3: backing-store error (local store unreadable / corrupt) ---
    error_root = tmp_path / "error_repo"
    (error_root / ".hotdocs").mkdir(parents=True)
    # The cache location is a regular file holding garbage, not a store.
    (error_root / ".hotdocs" / "cache").write_text("\x00not a cache store{{%%")
    errored = cache_manager.get(_key("3"), repo_root=error_root)

    # All three are definitive misses, never None, never a CachedResult.
    for outcome in (evicted, never_stored, errored):
        assert outcome is not None
        assert isinstance(outcome, cache_manager.Miss)
        assert not isinstance(outcome, cache_manager.CachedResult)

    # Indistinguishable in shape: same type, and all compare equal.
    assert type(evicted) is type(never_stored) is type(errored)
    assert evicted == never_stored
    assert evicted == errored
    assert never_stored == errored

    # The CLI reports the evicted key exactly as it reports a never-stored key.
    code_evicted, out_evicted = _inspect(evicted_key, evict_root, capsys)
    code_never, out_never = _inspect(_key("2"), never_root, capsys)
    assert code_evicted == 0
    assert code_never == 0
    assert len(out_evicted) == 1
    assert len(out_never) == 1
    assert json.loads(out_evicted[0]) == {"result": "miss"}
    assert json.loads(out_evicted[0]) == json.loads(out_never[0])