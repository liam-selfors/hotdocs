# hotdocs-criterion: sha256:91a3cc50603220dfc3925ca0793ed1857802bc52b266153d127703584e8fa9da
import io
import json
import contextlib

import pytest

import cache_manager


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def make_key(**overrides):
    values = {
        "spec_bundle_hash": "sha256:" + "a" * 64,
        "gate_inputs_hash": "sha256:" + "b" * 64,
        "gate_version": "license_scanner@4.0.3+9f2c41ab07de",
        "model_pin": "claude-sonnet-5",
    }
    values.update(overrides)
    return cache_manager.CacheKey(**values)


@pytest.fixture
def repo_root(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    root = tmp_path / "repo"
    root.mkdir()
    monkeypatch.chdir(root)
    return root


def test_get_on_empty_store_returns_miss(repo_root):
    result = cache_manager.get(make_key(), repo_root=repo_root)

    assert result is not None
    assert isinstance(result, cache_manager.Miss)
    assert not isinstance(result, cache_manager.CachedResult)
    assert result == cache_manager.Miss()


def test_get_for_unstored_key_returns_miss_not_near_match(repo_root):
    stored_key = make_key()
    stored = cache_manager.CachedResult(
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
    cache_manager.put(stored_key, stored, repo_root=repo_root)

    near_keys = [
        make_key(spec_bundle_hash="sha256:" + "c" * 64),
        make_key(gate_inputs_hash="sha256:" + "d" * 64),
        make_key(gate_version="license_scanner@4.0.4+9f2c41ab07de"),
        make_key(model_pin="claude-sonnet-5-5"),
    ]
    for key in near_keys:
        result = cache_manager.get(key, repo_root=repo_root)
        assert result is not None
        assert isinstance(result, cache_manager.Miss), key
        assert not isinstance(result, cache_manager.CachedResult)
        assert result == cache_manager.Miss()


def test_cli_inspect_on_empty_store_reports_miss(repo_root):
    out = io.StringIO()
    err = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = cache_manager.main([
            "inspect",
            "--spec-bundle-hash=sha256:" + "a" * 64,
            "--gate-inputs-hash=sha256:" + "b" * 64,
            "--gate-version=license_scanner@4.0.3+9f2c41ab07de",
            "--model-pin=claude-sonnet-5",
            "--repo-root=" + str(repo_root),
        ])

    assert code == 0
    lines = [line for line in out.getvalue().splitlines() if line.strip()]
    assert len(lines) == 1
    doc = json.loads(lines[0])
    assert doc == {"result": "miss"}