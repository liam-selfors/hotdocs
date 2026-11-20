# hotdocs-criterion: sha256:ad611088f435ec3218cc4e631fd2b00c8298f99e50cd46ae9d0488cdff33283f
import json
from pathlib import Path

import pytest

import cache_manager


STORE_URL = "redis://cache.internal:6379/0"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _key():
    return cache_manager.CacheKey(
        spec_bundle_hash="sha256:" + "a" * 64,
        gate_inputs_hash="sha256:" + "b" * 64,
        gate_version="license_scanner@4.0.3+9f2c41ab07de",
        model_pin="claude-sonnet-5",
    )


def _valid_result():
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


def _files_under(path):
    if not path.exists():
        return []
    return [p for p in path.rglob("*")]


def test_store_url_set_put_then_get_is_miss_and_nothing_stored(tmp_path, monkeypatch, capsys):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    cwd = tmp_path / "elsewhere"
    cwd.mkdir()
    monkeypatch.chdir(cwd)
    monkeypatch.setenv("VAR_CACHE_STORE_URL", STORE_URL)

    key = _key()
    cache_manager.put(key, _valid_result(), repo_root=repo_root)
    got = cache_manager.get(key, repo_root=repo_root)

    assert got is not None
    assert isinstance(got, cache_manager.Miss)

    cache_dir = repo_root / ".hotdocs" / "cache"
    assert _files_under(cache_dir) == []
    assert _files_under(cwd / ".hotdocs" / "cache") == []

    capsys.readouterr()
    code = cache_manager.main(["stats", "--repo-root=" + str(repo_root)])
    out = capsys.readouterr().out
    assert code == 0
    lines = [ln for ln in out.splitlines() if ln.strip()]
    assert len(lines) == 1
    assert json.loads(lines[0]) == {"entry_count": 0}

    stats = cache_manager.stats(repo_root=repo_root)
    assert field(stats, "entry_count") == 0


def test_store_url_set_put_with_missing_required_key_raises(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("VAR_CACHE_STORE_URL", STORE_URL)

    bad = cache_manager.CachedResult(
        gate_type="license_scanner",
        payload={
            "component_id": "comp-foo",
            "gate_version": "license_scanner@4.0.3+9f2c41ab07de",
            "similarity_score": 0.0,
            "blocked": False,
            # "matches" deliberately missing
        },
        stored_at=cache_manager.now_iso(),
    )

    with pytest.raises(cache_manager.SchemaValidationError):
        cache_manager.put(_key(), bad, repo_root=repo_root)

    assert issubclass(cache_manager.SchemaValidationError, ValueError)
    assert _files_under(repo_root / ".hotdocs" / "cache") == []