# hotdocs-criterion: sha256:78432b79dea04e80ef4b17c1fcde7e36c492373274cd39277fe0c55223321ada
"""AC-CACHE-010 (covers R-CACHE-009).

Given VAR-CACHE-STORE-URL is absent
When put is called for a key and then get is called for the same key
Then get returns the stored result, read back from .hotdocs/cache/,
  with no distinct code path required by the caller
"""

from pathlib import Path

import pytest

import cache_manager


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _make_key(suffix="a"):
    return cache_manager.CacheKey(
        spec_bundle_hash="sha256:" + ("1" * 63) + suffix,
        gate_inputs_hash="sha256:" + ("2" * 63) + suffix,
        gate_version="llm_judge@1.0.0+abcdef123456",
        model_pin="claude-sonnet-5",
    )


def _make_result():
    return cache_manager.CachedResult(
        gate_type="llm_judge",
        payload={"result": "pass", "rationale": "looks right"},
        stored_at=cache_manager.now_iso(),
    )


def _files_under(directory):
    if not directory.is_dir():
        return []
    return [p for p in directory.rglob("*") if p.is_file()]


def _assert_same_result(got, expected):
    assert not isinstance(got, cache_manager.Miss), "get returned Miss after put"
    assert got is not None
    assert field(got, "gate_type") == expected.gate_type
    assert field(got, "payload") == expected.payload
    assert field(got, "stored_at") == expected.stored_at


@pytest.mark.parametrize("absent_mode", ["unset", "empty"])
def test_put_then_get_round_trips_through_local_store(tmp_path, monkeypatch, absent_mode):
    if absent_mode == "unset":
        monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    else:
        monkeypatch.setenv("VAR_CACHE_STORE_URL", "")

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    cache_dir = repo_root / ".hotdocs" / "cache"

    key = _make_key()
    result = _make_result()

    # Before the put, the key is a miss.
    before = cache_manager.get(key, repo_root=repo_root)
    assert isinstance(before, cache_manager.Miss)

    assert cache_manager.put(key, result, repo_root=repo_root) is None

    # The local fallback actually wrote something under .hotdocs/cache/.
    assert cache_dir.is_dir(), ".hotdocs/cache/ was not created by put"
    assert len(_files_under(cache_dir)) >= 1, "nothing was written under .hotdocs/cache/"

    got = cache_manager.get(key, repo_root=repo_root)
    _assert_same_result(got, result)

    stats = cache_manager.stats(repo_root=repo_root)
    assert field(stats, "entry_count") >= 1


def test_get_reads_back_from_that_repos_hotdocs_cache(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)

    repo_a = tmp_path / "repo_a"
    repo_b = tmp_path / "repo_b"
    repo_a.mkdir()
    repo_b.mkdir()

    key = _make_key("b")
    result = _make_result()

    cache_manager.put(key, result, repo_root=repo_a)

    # Stored in repo_a's .hotdocs/cache/, not some process-wide memory store.
    _assert_same_result(cache_manager.get(key, repo_root=repo_a), result)
    assert isinstance(cache_manager.get(key, repo_root=repo_b), cache_manager.Miss)
    assert _files_under(repo_b / ".hotdocs" / "cache") == []

    # Removing repo_a's on-disk store makes the entry go away: it was read from disk.
    for p in sorted(_files_under(repo_a / ".hotdocs" / "cache"), reverse=True):
        p.unlink()
    assert isinstance(cache_manager.get(key, repo_root=repo_a), cache_manager.Miss)


def test_default_repo_root_uses_cwd_with_same_calls(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    monkeypatch.chdir(tmp_path)

    key = _make_key("c")
    result = _make_result()

    # Same call shape as any backing: no fallback-specific API needed.
    cache_manager.put(key, result)
    got = cache_manager.get(key)
    _assert_same_result(got, result)

    assert len(_files_under(Path(tmp_path) / ".hotdocs" / "cache")) >= 1