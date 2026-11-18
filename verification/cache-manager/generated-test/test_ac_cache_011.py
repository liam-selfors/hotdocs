# hotdocs-criterion: sha256:2eae1fa812edbd7e944d1e86b6368eef9275931200a7c30a2d446fe23601d20e
import json

import pytest

import cache_manager


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _make_key(suffix):
    return cache_manager.CacheKey(
        spec_bundle_hash="sha256:" + ("a" * 63) + suffix,
        gate_inputs_hash="sha256:" + ("b" * 63) + suffix,
        gate_version="license_scanner@4.0.3+9f2c41ab07de",
        model_pin="claude-sonnet-5",
    )


def _make_result():
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


def _stdout_json(out):
    lines = [line for line in out.splitlines() if line.strip()]
    assert lines, "expected one line of JSON on stdout, got nothing"
    return json.loads(lines[-1])


@pytest.fixture(autouse=True)
def _local_store_only(monkeypatch, tmp_path):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    monkeypatch.chdir(cwd)


def test_stats_empty_repo_root_reports_zero(tmp_path, capsys):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    code = cache_manager.main(["stats", "--repo-root=" + str(repo_root)])
    captured = capsys.readouterr()

    assert code == 0
    assert _stdout_json(captured.out) == {"entry_count": 0}


def test_stats_counts_distinct_keys_not_puts(tmp_path, capsys):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    key_one = _make_key("1")
    key_two = _make_key("2")

    cache_manager.put(key_one, _make_result(), repo_root=repo_root)
    cache_manager.put(key_two, _make_result(), repo_root=repo_root)
    cache_manager.put(key_two, _make_result(), repo_root=repo_root)

    # Sanity: both entries are actually retrievable from this repo_root.
    for key in (key_one, key_two):
        got = cache_manager.get(key, repo_root=repo_root)
        assert not isinstance(got, cache_manager.Miss)
        assert field(got, "gate_type") == "license_scanner"

    capsys.readouterr()
    code = cache_manager.main(["stats", "--repo-root", str(repo_root)])
    captured = capsys.readouterr()

    assert code == 0
    assert _stdout_json(captured.out) == {"entry_count": 2}