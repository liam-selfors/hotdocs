"""AC-CACHE-008: an entry evicted by the backing store after a successful put
(and before any get) yields a definitive miss on get, indistinguishable in
shape from a backing-store-error miss (R-CACHE-004) and a never-stored miss.
"""

import hashlib
import json
import os
import shutil
from pathlib import Path

import pytest

import cache_manager


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _sha(text):
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def _key(tag):
    return cache_manager.CacheKey(
        spec_bundle_hash=_sha("bundle-" + tag),
        gate_inputs_hash=_sha("inputs-" + tag),
        gate_version="llm_judge@1.0.0",
        model_pin="claude-sonnet-5",
    )


def _result():
    return cache_manager.CachedResult(
        gate_type="llm_judge",
        payload={"result": "pass", "rationale": "looks fine"},
        stored_at=cache_manager.now_iso(),
    )


def _evict_everything(cache_dir):
    """Simulate the backing store evicting its entries on its own."""
    for child in list(cache_dir.iterdir()):
        if child.is_dir() and not child.is_symlink():
            shutil.rmtree(child)
        else:
            child.unlink()


def _inspect_cli(capsys, key, repo_root):
    capsys.readouterr()
    code = cache_manager.main(
        [
            "inspect",
            "--spec-bundle-hash=" + field(key, "spec_bundle_hash"),
            "--gate-inputs-hash=" + field(key, "gate_inputs_hash"),
            "--gate-version=" + field(key, "gate_version"),
            "--model-pin=" + field(key, "model_pin"),
            "--repo-root=" + str(repo_root),
        ]
    )
    out = capsys.readouterr().out.strip().splitlines()
    assert out, "inspect printed nothing"
    return code, json.loads(out[-1])


def test_evicted_entry_is_a_plain_miss_identical_to_other_misses(
    tmp_path, monkeypatch, capsys
):
    # Use the local fallback store so the test controls the backing store.
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)

    repo = tmp_path / "repo"
    repo.mkdir()
    monkeypatch.chdir(repo)

    evicted_key = _key("evicted")
    never_key = _key("never-stored")

    # Given: a key that was successfully put.
    assert cache_manager.put(evicted_key, _result(), repo_root=repo) is None

    cache_dir = repo / ".hotdocs" / "cache"
    assert cache_dir.is_dir(), "local fallback store did not write under .hotdocs/cache/"
    assert any(p.is_file() for p in cache_dir.rglob("*")), "put stored nothing"
    assert field(cache_manager.stats(repo_root=repo), "entry_count") >= 1

    # ...then evicted by the backing store, before any get for it.
    _evict_everything(cache_dir)
    assert field(cache_manager.stats(repo_root=repo), "entry_count") == 0

    # When: get is called with that key.
    evicted_miss = cache_manager.get(evicted_key, repo_root=repo)

    # A key that was simply never stored.
    never_miss = cache_manager.get(never_key, repo_root=repo)

    # A backing-store error: the store location is unusable (a file where
    # the cache directory should be).
    broken = tmp_path / "broken"
    (broken / ".hotdocs").mkdir(parents=True)
    (broken / ".hotdocs" / "cache").write_text("not a directory\n")
    error_miss = cache_manager.get(evicted_key, repo_root=broken)

    # Then: a definitive miss, never None or an approximation.
    for r in (evicted_miss, never_miss, error_miss):
        assert r is not None
        assert isinstance(r, cache_manager.Miss)
        assert not isinstance(r, cache_manager.CachedResult)

    # Indistinguishable in shape across all three cases.
    assert type(evicted_miss) is type(never_miss) is type(error_miss)
    assert evicted_miss == never_miss
    assert evicted_miss == error_miss
    assert never_miss == error_miss
    assert evicted_miss == cache_manager.Miss()

    # The caller's handling is identical: the CLI reports the same answer.
    code_evicted, out_evicted = _inspect_cli(capsys, evicted_key, repo)
    code_never, out_never = _inspect_cli(capsys, never_key, repo)
    code_error, out_error = _inspect_cli(capsys, evicted_key, broken)

    assert code_evicted == code_never == code_error == 0
    assert out_evicted == {"result": "miss"}
    assert out_never == {"result": "miss"}
    assert out_error == {"result": "miss"}