"""AC-CACHE-010 (Covers: R-CACHE-009).

Given VAR-CACHE-STORE-URL is absent
When put is called for a key and then get is called for the same key
Then get returns the stored result, read back from .hotdocs/cache/,
  with no distinct code path required by the caller
"""

import cache_manager

from pathlib import Path


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
        "similarity_score": 0.125,
        "blocked": False,
        "matches": [{"source": "x", "score": 0.125}],
    }
    return cache_manager.CachedResult(
        gate_type="license_scanner",
        payload=payload,
        stored_at=cache_manager.now_iso(),
    ), payload


def _files_under(directory: Path):
    if not directory.is_dir():
        return []
    return [p for p in directory.rglob("*") if p.is_file()]


def _assert_same_result(got, expected_payload, expected_stored_at):
    assert not isinstance(got, cache_manager.Miss), "expected a hit, got Miss"
    assert got is not None
    assert field(got, "gate_type") == "license_scanner"
    got_payload = field(got, "payload")
    assert dict(got_payload) == expected_payload
    assert field(got, "stored_at") == expected_stored_at


def _clear_store_url(monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    monkeypatch.delenv("VAR-CACHE-STORE-URL", raising=False)


def test_put_then_get_round_trips_through_local_store(tmp_path, monkeypatch):
    _clear_store_url(monkeypatch)

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    other_root = tmp_path / "other"
    other_root.mkdir()

    key = _make_key()
    result, payload = _make_result()
    stored_at = field(result, "stored_at")

    # Before any put, the key is a miss.
    before = cache_manager.get(key, repo_root=repo_root)
    assert isinstance(before, cache_manager.Miss)

    ret = cache_manager.put(key, result, repo_root=repo_root)
    assert ret is None

    # The local fallback wrote its data under <repo_root>/.hotdocs/cache/.
    cache_dir = repo_root / ".hotdocs" / "cache"
    assert cache_dir.is_dir(), ".hotdocs/cache/ was not created by put"
    assert _files_under(cache_dir), "put stored nothing under .hotdocs/cache/"

    # get for the same key returns the stored result — same call shape as
    # any other backing, no extra argument or alternate function.
    got = cache_manager.get(key, repo_root=repo_root)
    _assert_same_result(got, payload, stored_at)

    # The data is read back from this repo's .hotdocs/cache/: a different
    # repo_root (with its own empty .hotdocs/cache/) does not see it.
    elsewhere = cache_manager.get(key, repo_root=other_root)
    assert isinstance(elsewhere, cache_manager.Miss)

    # The local store reports the entry it holds.
    s = cache_manager.stats(repo_root=repo_root)
    assert field(s, "entry_count") >= 1


def test_put_then_get_with_default_repo_root_uses_cwd(tmp_path, monkeypatch):
    _clear_store_url(monkeypatch)
    monkeypatch.chdir(tmp_path)

    key = _make_key(suffix="b")
    result, payload = _make_result()
    stored_at = field(result, "stored_at")

    # Caller uses the plain contract with no backing-specific arguments.
    cache_manager.put(key, result)
    got = cache_manager.get(key)
    _assert_same_result(got, payload, stored_at)

    cache_dir = tmp_path / ".hotdocs" / "cache"
    assert cache_dir.is_dir()
    assert _files_under(cache_dir)

    # The same entry is visible via an explicit repo_root pointing at cwd.
    got_explicit = cache_manager.get(key, repo_root=tmp_path)
    _assert_same_result(got_explicit, payload, stored_at)


def test_empty_store_url_counts_as_absent(tmp_path, monkeypatch):
    # Unset or empty means absent (glossary: Var environment name).
    monkeypatch.setenv("VAR_CACHE_STORE_URL", "")

    key = _make_key(suffix="c")
    result, payload = _make_result()
    stored_at = field(result, "stored_at")

    cache_manager.put(key, result, repo_root=tmp_path)
    got = cache_manager.get(key, repo_root=tmp_path)
    _assert_same_result(got, payload, stored_at)
    assert _files_under(tmp_path / ".hotdocs" / "cache")