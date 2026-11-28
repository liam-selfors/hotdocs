# hotdocs-criterion: sha256:5137a18d95f5cdb4cfab2e5478efae78fce93e6baab6ab0ed46a8c8f1893d755
import json

import pytest

import cache_manager


def _stdout_json(capsys):
    out = capsys.readouterr().out
    lines = [line for line in out.splitlines() if line.strip()]
    assert len(lines) == 1, "expected exactly one line of stdout, got: " + repr(out)
    return json.loads(lines[0])


def _key(spec_hash):
    return cache_manager.CacheKey(
        spec_bundle_hash=spec_hash,
        gate_inputs_hash="sha256:" + "b" * 64,
        gate_version="llm_judge@1.0.0",
        model_pin="claude-sonnet-5",
    )


def _result():
    return cache_manager.CachedResult(
        gate_type="llm_judge",
        payload={"result": "pass", "rationale": "ok"},
        stored_at=cache_manager.now_iso(),
    )


@pytest.fixture(autouse=True)
def _no_remote_store(monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)


def test_stats_empty_repo_root_reports_zero(tmp_path, capsys, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(tmp_path)

    code = cache_manager.main(["stats", "--repo-root=" + str(repo_root)])

    assert code == 0
    assert _stdout_json(capsys) == {"entry_count": 0}


def test_stats_counts_distinct_keys_once(tmp_path, capsys, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(tmp_path)

    key_a = _key("sha256:" + "a" * 64)
    key_b = _key("sha256:" + "c" * 64)

    cache_manager.put(key_a, _result(), repo_root=repo_root)
    cache_manager.put(key_b, _result(), repo_root=repo_root)
    cache_manager.put(key_a, _result(), repo_root=repo_root)

    capsys.readouterr()

    code = cache_manager.main(["stats", "--repo-root", str(repo_root)])

    assert code == 0
    assert _stdout_json(capsys) == {"entry_count": 2}