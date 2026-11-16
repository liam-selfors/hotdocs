import os
import shutil
from pathlib import Path

import pytest

import cache_manager


def _field(value, name):
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def _make_key(suffix="a"):
    return cache_manager.CacheKey(
        spec_bundle_hash="sha256:" + ("1" * 63) + suffix,
        gate_inputs_hash="sha256:" + ("2" * 63) + suffix,
        gate_version="license_scanner@4.0.3+9f2c41ab07de",
        model_pin="claude-sonnet-5",
    )


def _make_result():
    return cache_manager.CachedResult(
        gate_type="license_scanner",
        payload={
            "component_id": "comp-example",
            "gate_version": "license_scanner@4.0.3+9f2c41ab07de",
            "similarity_score": 0.12,
            "blocked": False,
            "matches": [],
        },
        stored_at=cache_manager.now_iso(),
    )


def _cache_files(repo_root):
    cache_dir = Path(repo_root) / ".hotdocs" / "cache"
    if not cache_dir.is_dir():
        return []
    return [p for p in cache_dir.rglob("*") if p.is_file()]


def _assert_hit_matches(got, expected):
    assert got is not None
    assert not isinstance(got, cache_manager.Miss), "expected a hit, got Miss"
    assert _field(got, "gate_type") == expected.gate_type
    assert _field(got, "payload") == expected.payload
    assert _field(got, "stored_at") == expected.stored_at


def _set_store_absent(monkeypatch, mode):
    if mode == "unset":
        monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    else:
        monkeypatch.setenv("VAR_CACHE_STORE_URL", "")


@pytest.mark.parametrize("mode", ["unset", "empty"])
def test_put_then_get_round_trips_through_local_store(tmp_path, monkeypatch, mode):
    _set_store_absent(monkeypatch, mode)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    key = _make_key()
    result = _make_result()

    before = cache_manager.get(key, repo_root=repo_root)
    assert isinstance(before, cache_manager.Miss)

    ret = cache_manager.put(key, result, repo_root=repo_root)
    assert ret is None

    files = _cache_files(repo_root)
    assert files, "put must persist the entry under <repo_root>/.hotdocs/cache/"

    got = cache_manager.get(key, repo_root=repo_root)
    _assert_hit_matches(got, result)

    stats = cache_manager.stats(repo_root=repo_root)
    entry_count = _field(stats, "entry_count")
    assert isinstance(entry_count, int)
    assert entry_count >= 1


def test_hit_is_read_back_from_disk_not_process_memory(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    repo_a = tmp_path / "repo_a"
    repo_b = tmp_path / "repo_b"
    repo_c = tmp_path / "repo_c"
    for d in (repo_a, repo_b, repo_c):
        d.mkdir()

    key = _make_key("b")
    result = _make_result()
    cache_manager.put(key, result, repo_root=repo_a)
    assert _cache_files(repo_a)

    # A different repo that never had a put, and whose disk store is empty,
    # must not see the entry.
    assert isinstance(cache_manager.get(key, repo_root=repo_c), cache_manager.Miss)

    # Copying only the on-disk .hotdocs/cache/ into a fresh repo must be
    # sufficient for a hit there: the data lives in the files.
    shutil.copytree(repo_a / ".hotdocs" / "cache", repo_b / ".hotdocs" / "cache")
    got = cache_manager.get(key, repo_root=repo_b)
    _assert_hit_matches(got, result)


def test_default_repo_root_uses_cwd_without_distinct_caller_path(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    repo_root = tmp_path / "cwd_repo"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)

    key = _make_key("c")
    result = _make_result()

    # Same call shape a caller would use with a shared store configured:
    # no backing-specific argument at all.
    cache_manager.put(key, result)
    got = cache_manager.get(key)
    _assert_hit_matches(got, result)

    assert _cache_files(repo_root), "default repo_root must resolve to the cwd's .hotdocs/cache/"


def test_distinct_keys_do_not_collide_in_local_store(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    key1 = _make_key("d")
    key2 = _make_key("e")
    result = _make_result()

    cache_manager.put(key1, result, repo_root=repo_root)
    _assert_hit_matches(cache_manager.get(key1, repo_root=repo_root), result)
    assert isinstance(cache_manager.get(key2, repo_root=repo_root), cache_manager.Miss)