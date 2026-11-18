# hotdocs-criterion: sha256:65629ece68040f74bee358f16abb976e10e157c59f7914d1c9fe297a996424f5
import json
from pathlib import Path

import pytest

import cache_manager


STORE_URL = "redis://cache.internal:6379/0"


def _key(gate_type="license_scanner"):
    return cache_manager.CacheKey(
        spec_bundle_hash="sha256:" + "a" * 64,
        gate_inputs_hash="sha256:" + "b" * 64,
        gate_version=f"{gate_type}@4.0.3+9f2c41ab07de",
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


def _files_under(path: Path):
    if not path.exists():
        return []
    if path.is_file():
        return [path]
    return list(path.rglob("*"))


@pytest.fixture
def repo_root(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    root.mkdir()
    monkeypatch.chdir(root)
    monkeypatch.setenv("VAR_CACHE_STORE_URL", STORE_URL)
    return root


def test_store_url_set_put_then_get_is_miss_and_nothing_stored(repo_root, capsys):
    key = _key()
    result = _valid_result()

    # put must not crash, even though the shared store is unreachable
    ret = cache_manager.put(key, result, repo_root=repo_root)
    assert ret is None

    got = cache_manager.get(key, repo_root=repo_root)
    assert got is not None
    assert isinstance(got, cache_manager.Miss)
    assert got == cache_manager.Miss()

    cache_dir = repo_root / ".hotdocs" / "cache"
    assert _files_under(cache_dir) == [], (
        f"expected nothing under {cache_dir}, found {_files_under(cache_dir)}"
    )

    capsys.readouterr()
    code = cache_manager.main(["stats", f"--repo-root={repo_root}"])
    out = capsys.readouterr().out
    assert code == 0
    lines = [ln for ln in out.splitlines() if ln.strip()]
    assert lines, "stats printed nothing"
    assert json.loads(lines[-1]) == {"entry_count": 0}

    # Still nothing written after stats either
    assert _files_under(cache_dir) == []


def test_store_url_set_put_with_missing_required_key_raises(repo_root):
    key = _key()
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
        cache_manager.put(key, bad, repo_root=repo_root)

    assert issubclass(cache_manager.SchemaValidationError, ValueError)
    assert _files_under(repo_root / ".hotdocs" / "cache") == []