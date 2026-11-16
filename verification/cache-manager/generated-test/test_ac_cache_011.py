import json

import pytest

import cache_manager


def _field(value, name):
    return value.get(name) if isinstance(value, dict) else getattr(value, name, None)


def _last_json_line(captured_out):
    lines = [ln for ln in captured_out.splitlines() if ln.strip()]
    assert lines, "expected one line of JSON on stdout, got nothing"
    return json.loads(lines[-1])


def _make_key(suffix):
    return cache_manager.CacheKey(
        spec_bundle_hash="sha256:" + ("a" * 63) + suffix,
        gate_inputs_hash="sha256:" + ("b" * 63) + suffix,
        gate_version="license_scanner@4.0.3+9f2c41ab07de",
        model_pin="claude-sonnet-5",
    )


def _make_result(score):
    return cache_manager.CachedResult(
        gate_type="license_scanner",
        payload={
            "component_id": "comp-example",
            "gate_version": "license_scanner@4.0.3+9f2c41ab07de",
            "similarity_score": score,
            "blocked": False,
            "matches": [],
        },
        stored_at=cache_manager.now_iso(),
    )


@pytest.fixture
def isolated_env(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    cwd = tmp_path / "unrelated_cwd"
    cwd.mkdir()
    monkeypatch.chdir(cwd)
    repo_root = tmp_path / "repo_root"
    repo_root.mkdir()
    return repo_root


def test_stats_on_empty_repo_root_reports_zero(isolated_env, capsys):
    repo_root = isolated_env
    capsys.readouterr()
    code = cache_manager.main(["stats", "--repo-root=" + str(repo_root)])
    out = capsys.readouterr().out
    assert code == 0
    data = _last_json_line(out)
    assert data == {"entry_count": 0}


def test_stats_counts_distinct_keys_not_puts(isolated_env, capsys):
    repo_root = isolated_env
    key_one = _make_key("1")
    key_two = _make_key("2")

    cache_manager.put(key_one, _make_result(0.1), repo_root=repo_root)
    cache_manager.put(key_two, _make_result(0.2), repo_root=repo_root)
    # Same key put a second time: overwrites (last-write-wins), not a new entry.
    cache_manager.put(key_one, _make_result(0.3), repo_root=repo_root)

    capsys.readouterr()
    code = cache_manager.main(["stats", "--repo-root", str(repo_root)])
    out = capsys.readouterr().out
    assert code == 0
    data = _last_json_line(out)
    assert data == {"entry_count": 2}
    assert _field(data, "entry_count") == 2