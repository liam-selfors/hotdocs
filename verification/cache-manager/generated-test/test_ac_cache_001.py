import json
import os
import sys

import pytest

import cache_manager


def _field(value, name):
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def _make_key(**overrides):
    fields = {
        "spec_bundle_hash": "sha256:" + "a" * 64,
        "gate_inputs_hash": "sha256:" + "b" * 64,
        "gate_version": "license_scanner@4.0.3+9f2c41ab07de",
        "model_pin": "claude-sonnet-5",
    }
    fields.update(overrides)
    return cache_manager.CacheKey(**fields)


def _make_result():
    payload = {
        "component_id": "comp-example",
        "gate_version": "license_scanner@4.0.3+9f2c41ab07de",
        "similarity_score": 0.0,
        "blocked": False,
        "matches": [],
    }
    return cache_manager.CachedResult(
        gate_type="license_scanner",
        payload=payload,
        stored_at=cache_manager.now_iso(),
    )


@pytest.fixture
def isolated_repo(tmp_path, monkeypatch):
    # Force the local fallback store (R-CACHE-009) under a fresh, empty repo root.
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)
    return repo_root


def _assert_definitive_miss(result):
    assert result is not None, "get must report a miss with a Miss instance, never None"
    assert isinstance(result, cache_manager.Miss), (
        "expected a Miss instance, got %r" % (result,)
    )
    assert not isinstance(result, cache_manager.CachedResult), (
        "a miss must not be a (partial) CachedResult"
    )
    # Not a partial result: no payload / gate_type / stored_at carried on the miss.
    assert _field(result, "payload") is None
    assert _field(result, "gate_type") is None
    assert _field(result, "stored_at") is None
    # Any two Miss instances compare equal.
    assert result == cache_manager.Miss()


def test_get_on_empty_store_returns_miss(isolated_repo):
    key = _make_key()
    result = cache_manager.get(key, repo_root=isolated_repo)
    _assert_definitive_miss(result)


def test_get_on_empty_store_with_default_repo_root_returns_miss(isolated_repo):
    key = _make_key()
    result = cache_manager.get(key)
    _assert_definitive_miss(result)


def test_get_for_unstored_key_is_miss_even_when_near_match_exists(isolated_repo):
    stored_key = _make_key()
    cache_manager.put(stored_key, _make_result(), repo_root=isolated_repo)

    # Sanity: the stored key itself is a hit, so the store is actually working.
    hit = cache_manager.get(stored_key, repo_root=isolated_repo)
    assert not isinstance(hit, cache_manager.Miss)
    assert _field(hit, "gate_type") == "license_scanner"

    near_keys = [
        _make_key(spec_bundle_hash="sha256:" + "c" * 64),
        _make_key(gate_inputs_hash="sha256:" + "d" * 64),
        _make_key(gate_version="license_scanner@4.0.4+9f2c41ab07de"),
        _make_key(model_pin="claude-sonnet-5-5"),
    ]
    for near_key in near_keys:
        result = cache_manager.get(near_key, repo_root=isolated_repo)
        _assert_definitive_miss(result)


def test_cli_inspect_on_empty_store_reports_miss(isolated_repo, capsys):
    argv = [
        "inspect",
        "--spec-bundle-hash=sha256:" + "a" * 64,
        "--gate-inputs-hash=sha256:" + "b" * 64,
        "--gate-version=license_scanner@4.0.3+9f2c41ab07de",
        "--model-pin=claude-sonnet-5",
        "--repo-root=" + str(isolated_repo),
    ]
    code = cache_manager.main(argv)
    captured = capsys.readouterr()
    assert code == 0, "a miss is an answer, not a failure: %r" % (captured,)
    lines = [ln for ln in captured.out.splitlines() if ln.strip()]
    assert lines, "expected one line of JSON on stdout"
    data = json.loads(lines[-1])
    assert data.get("result") == "miss"
    assert "payload" not in data
    assert "gate_type" not in data
    assert "stored_at" not in data