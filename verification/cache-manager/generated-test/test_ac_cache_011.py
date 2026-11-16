import json

import pytest

import cache_manager


def _parse_stdout_json(out):
    lines = [line for line in out.splitlines() if line.strip()]
    assert lines, "expected one line of JSON on stdout, got nothing"
    return json.loads(lines[-1])


def _make_key(suffix):
    return cache_manager.CacheKey(
        spec_bundle_hash="sha256:" + ("a" * 63) + suffix,
        gate_inputs_hash="sha256:" + ("b" * 63) + suffix,
        gate_version="llm_judge@1.0.0+abcdef012345",
        model_pin="claude-sonnet-5",
    )


def _make_result(verdict):
    return cache_manager.CachedResult(
        gate_type="llm_judge",
        payload={"result": verdict, "rationale": "synthetic test rationale"},
        stored_at=cache_manager.now_iso(),
    )


@pytest.fixture
def repo_root(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    root.mkdir()
    # Ensure the local store is the one in use, not a remote backing store.
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    # Isolate any cwd-defaulted behavior from the real working directory.
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    return root


def test_stats_on_empty_repo_root_returns_zero_and_prints_zero_count(repo_root, capsys):
    capsys.readouterr()
    rc = cache_manager.main(["stats", "--repo-root=" + str(repo_root)])
    out = capsys.readouterr().out
    assert rc == 0
    assert _parse_stdout_json(out) == {"entry_count": 0}


def test_stats_counts_distinct_keys_not_puts(repo_root, capsys):
    key_one = _make_key("1")
    key_two = _make_key("2")

    cache_manager.put(key_one, _make_result("pass"), repo_root=repo_root)
    cache_manager.put(key_two, _make_result("pass"), repo_root=repo_root)
    # Same key put a second time: last-write-wins, still one entry.
    cache_manager.put(key_one, _make_result("fail"), repo_root=repo_root)

    capsys.readouterr()
    rc = cache_manager.main(["stats", "--repo-root", str(repo_root)])
    out = capsys.readouterr().out
    assert rc == 0
    assert _parse_stdout_json(out) == {"entry_count": 2}