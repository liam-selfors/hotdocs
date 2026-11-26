# hotdocs-criterion: sha256:805751babd50d195523401d23262019d2a37fd1e74dc43d56f2298efd07cbfd8
"""AC-CACHE-010 (covers R-CACHE-009).

Given VAR-CACHE-STORE-URL is absent
When put is called for a key and then get is called for the same key
Then get returns the stored result, read back from .hotdocs/cache/,
  with no distinct code path required by the caller
"""

import shutil
from pathlib import Path

import pytest

import cache_manager


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _make_key(suffix="a"):
    return cache_manager.CacheKey(
        spec_bundle_hash="sha256:" + ("1" * 63) + suffix,
        gate_inputs_hash="sha256:" + ("2" * 63) + suffix,
        gate_version="license_scanner@4.0.3+9f2c41ab07de",
        model_pin="claude-sonnet-5",
    )


def _make_result():
    payload = {
        "component_id": "comp-example",
        "gate_version": "license_scanner@4.0.3+9f2c41ab07de",
        "similarity_score": 0.12,
        "blocked": False,
        "matches": [],
    }
    return cache_manager.CachedResult(
        gate_type="license_scanner",
        payload=payload,
        stored_at=cache_manager.now_iso(),
    )


def _files_under(directory):
    if not directory.is_dir():
        return []
    return [p for p in directory.rglob("*") if p.is_file()]


@pytest.fixture(params=["unset", "empty"])
def store_url_absent(request, monkeypatch):
    # Unset or empty both mean "absent" (glossary, D164).
    if request.param == "unset":
        monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    else:
        monkeypatch.setenv("VAR_CACHE_STORE_URL", "")
    # The hyphenated name must never be consulted; make sure it is not set either.
    monkeypatch.delenv("VAR-CACHE-STORE-URL", raising=False)
    return request.param


def test_put_then_get_round_trips_through_local_store(store_url_absent, tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    key = _make_key()
    result = _make_result()

    # Before any put, the key is a miss.
    before = cache_manager.get(key, repo_root=repo_root)
    assert isinstance(before, cache_manager.Miss)

    # Same public calls a caller would use with a shared store: no distinct code path.
    assert cache_manager.put(key, result, repo_root=repo_root) is None

    cache_dir = repo_root / ".hotdocs" / "cache"
    written = _files_under(cache_dir)
    assert written, "put wrote nothing under " + str(cache_dir)

    got = cache_manager.get(key, repo_root=repo_root)
    assert not isinstance(got, cache_manager.Miss), "get missed after put with no store URL"
    assert got is not None
    assert field(got, "gate_type") == "license_scanner"
    assert field(got, "payload") == field(result, "payload")
    assert field(got, "stored_at") == field(result, "stored_at")

    # The local store reports holding the entry.
    stats = cache_manager.stats(repo_root=repo_root)
    assert field(stats, "entry_count") >= 1


def test_get_reads_back_from_repo_roots_hotdocs_cache(store_url_absent, tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    other_root = tmp_path / "other"
    other_root.mkdir()

    key = _make_key("b")
    result = _make_result()

    cache_manager.put(key, result, repo_root=repo_root)

    # The stored result lives in this repo_root's .hotdocs/cache/, not elsewhere.
    other = cache_manager.get(key, repo_root=other_root)
    assert isinstance(other, cache_manager.Miss)

    got = cache_manager.get(key, repo_root=repo_root)
    assert not isinstance(got, cache_manager.Miss)
    assert field(got, "payload") == field(result, "payload")

    # Removing .hotdocs/cache/ removes the entry: get really reads back from disk.
    shutil.rmtree(repo_root / ".hotdocs" / "cache")
    after = cache_manager.get(key, repo_root=repo_root)
    assert isinstance(after, cache_manager.Miss)


def test_cache_dir_copied_to_new_root_serves_hit(store_url_absent, tmp_path):
    src_root = tmp_path / "src"
    src_root.mkdir()
    dst_root = tmp_path / "dst"
    dst_root.mkdir()

    key = _make_key("c")
    result = _make_result()
    cache_manager.put(key, result, repo_root=src_root)

    # The on-disk contents alone are sufficient to answer get.
    shutil.copytree(src_root / ".hotdocs" / "cache", dst_root / ".hotdocs" / "cache")

    got = cache_manager.get(key, repo_root=dst_root)
    assert not isinstance(got, cache_manager.Miss)
    assert field(got, "gate_type") == "license_scanner"
    assert field(got, "payload") == field(result, "payload")
    assert field(got, "stored_at") == field(result, "stored_at")