# hotdocs-criterion: sha256:65629ece68040f74bee358f16abb976e10e157c59f7914d1c9fe297a996424f5
import json
import os
from pathlib import Path

import pytest

import cache_manager


STORE_URL = "redis://cache.internal:6379/0"
GATE_VERSION = "license_scanner@4.0.3+9f2c41ab07de"


def _make_key():
    return cache_manager.CacheKey(
        spec_bundle_hash="sha256:" + "a" * 64,
        gate_inputs_hash="sha256:" + "b" * 64,
        gate_version=GATE_VERSION,
        model_pin="claude-sonnet-5",
    )


def _valid_result():
    return cache_manager.CachedResult(
        gate_type="license_scanner",
        payload={
            "component_id": "comp-example",
            "gate_version": GATE_VERSION,
            "similarity_score": 0.0,
            "blocked": False,
            "matches": [],
        },
        stored_at=cache_manager.now_iso(),
    )


def _invalid_result():
    # Missing the required "matches" key for license_scanner.
    return cache_manager.CachedResult(
        gate_type="license_scanner",
        payload={
            "component_id": "comp-example",
            "gate_version": GATE_VERSION,
            "similarity_score": 0.0,
            "blocked": False,
        },
        stored_at=cache_manager.now_iso(),
    )


def _entries_under(path: Path):
    if not path.exists():
        return []
    found = []
    for root, dirs, files in os.walk(path):
        for d in dirs:
            found.append(os.path.join(root, d))
        for f in files:
            found.append(os.path.join(root, f))
    return found


def _field(value, name):
    return value.get(name) if isinstance(value, dict) else getattr(value, name, None)


def _last_json_line(text):
    lines = [ln for ln in text.splitlines() if ln.strip()]
    assert lines, "expected one line of JSON on stdout, got nothing"
    return json.loads(lines[-1])


@pytest.fixture
def repo_root(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    root.mkdir()
    cwd = tmp_path / "elsewhere"
    cwd.mkdir()
    monkeypatch.chdir(cwd)
    monkeypatch.setenv("VAR_CACHE_STORE_URL", STORE_URL)
    return root


def test_store_url_set_get_returns_miss_and_nothing_stored(repo_root, capsys):
    key = _make_key()
    result = _valid_result()

    ret = cache_manager.put(key, result, repo_root=repo_root)
    assert ret is None

    got = cache_manager.get(key, repo_root=repo_root)
    assert got is not None
    assert isinstance(got, cache_manager.Miss), (
        "get must return a Miss instance when VAR_CACHE_STORE_URL is set, got %r" % (got,)
    )
    assert got == cache_manager.Miss()

    cache_dir = repo_root / ".hotdocs" / "cache"
    entries = _entries_under(cache_dir)
    assert entries == [], "nothing may exist under .hotdocs/cache/, found: %r" % (entries,)

    capsys.readouterr()
    code = cache_manager.main(["stats", "--repo-root=%s" % repo_root])
    out = capsys.readouterr().out
    assert code == 0
    parsed = _last_json_line(out)
    assert parsed == {"entry_count": 0}

    lib_stats = cache_manager.stats(repo_root=repo_root)
    assert _field(lib_stats, "entry_count") == 0

    # Still nothing written after the stats call either.
    assert _entries_under(cache_dir) == []


def test_store_url_set_put_still_raises_schema_validation_error(repo_root):
    key = _make_key()
    bad = _invalid_result()

    with pytest.raises(cache_manager.SchemaValidationError):
        cache_manager.put(key, bad, repo_root=repo_root)

    assert issubclass(cache_manager.SchemaValidationError, ValueError)

    cache_dir = repo_root / ".hotdocs" / "cache"
    assert _entries_under(cache_dir) == []

    got = cache_manager.get(key, repo_root=repo_root)
    assert isinstance(got, cache_manager.Miss)