"""AC-CACHE-008 (covers R-CACHE-008).

Given a key that was successfully put, then evicted by the backing store
before any get for it, when get is called with that key, then it returns a
definitive miss, indistinguishable in shape from a backing-store error
(R-CACHE-004) or a key that was simply never stored.
"""

import json
import os
from pathlib import Path

import pytest

import cache_manager


GATE_VERSION = "license_scanner@4.0.3+9f2c41ab07de"
MODEL_PIN = "claude-sonnet-5"


def _key(suffix: str):
    return cache_manager.CacheKey(
        spec_bundle_hash="sha256:" + ("a" * 63) + suffix,
        gate_inputs_hash="sha256:" + ("b" * 63) + suffix,
        gate_version=GATE_VERSION,
        model_pin=MODEL_PIN,
    )


def _result():
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


def _field(value, name):
    return value.get(name) if isinstance(value, dict) else getattr(value, name, None)


def _is_miss(value):
    return isinstance(value, cache_manager.Miss)


def _evict_everything(repo_root: Path):
    """Simulate the backing store evicting its entries: remove every stored
    file under the local fallback store's directory, leaving no entry behind."""
    cache_dir = repo_root / ".hotdocs" / "cache"
    if not cache_dir.exists():
        return
    for dirpath, _dirnames, filenames in os.walk(cache_dir):
        for name in filenames:
            try:
                (Path(dirpath) / name).unlink()
            except FileNotFoundError:
                pass


def _cli_inspect(repo_root: Path, key, capsys):
    capsys.readouterr()
    code = cache_manager.main(
        [
            "inspect",
            "--spec-bundle-hash=" + _field(key, "spec_bundle_hash"),
            "--gate-inputs-hash=" + _field(key, "gate_inputs_hash"),
            "--gate-version=" + _field(key, "gate_version"),
            "--model-pin=" + _field(key, "model_pin"),
            "--repo-root=" + str(repo_root),
        ]
    )
    out = capsys.readouterr().out
    lines = [ln for ln in out.splitlines() if ln.strip()]
    assert lines, "inspect printed nothing on stdout"
    return code, json.loads(lines[-1])


@pytest.fixture
def isolated_env(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_evicted_key_returns_definitive_miss(isolated_env):
    repo_root = isolated_env / "repo-evicted"
    repo_root.mkdir()
    key = _key("1")

    cache_manager.put(key, _result(), repo_root=repo_root)

    # R-CACHE-008 permits eviction at any time, so a hit here is not
    # required; we only proceed to simulate the eviction regardless.
    _evict_everything(repo_root)

    result = cache_manager.get(key, repo_root=repo_root)
    assert result is not None, "get must never report a miss as None"
    assert _is_miss(result), f"expected a Miss after eviction, got {result!r}"


def test_evicted_miss_indistinguishable_from_never_stored_and_store_error(
    isolated_env, capsys
):
    # Case 1: put, then evicted before any get.
    evicted_root = isolated_env / "repo-evicted"
    evicted_root.mkdir()
    evicted_key = _key("2")
    cache_manager.put(evicted_key, _result(), repo_root=evicted_root)
    _evict_everything(evicted_root)
    evicted = cache_manager.get(evicted_key, repo_root=evicted_root)

    # Case 2: a key that was simply never stored.
    never_root = isolated_env / "repo-never"
    never_root.mkdir()
    never_key = _key("3")
    never = cache_manager.get(never_key, repo_root=never_root)

    # Case 3: a backing-store error — the local store's directory path is
    # occupied by a regular file, so the store cannot be read at all.
    error_root = isolated_env / "repo-error"
    (error_root / ".hotdocs").mkdir(parents=True)
    (error_root / ".hotdocs" / "cache").write_text("not a directory\n")
    error_key = _key("4")
    errored = cache_manager.get(error_key, repo_root=error_root)

    for label, value in (
        ("evicted", evicted),
        ("never-stored", never),
        ("backing-store-error", errored),
    ):
        assert value is not None, f"{label}: get must never return None"
        assert _is_miss(value), f"{label}: expected a Miss, got {value!r}"

    # Indistinguishable in shape: same type, and all compare equal.
    assert type(evicted) is type(never) is type(errored)
    assert evicted == never
    assert never == errored
    assert evicted == errored

    # The same holds at the CLI surface: identical exit code and output.
    cli_results = [
        _cli_inspect(evicted_root, evicted_key, capsys),
        _cli_inspect(never_root, never_key, capsys),
        _cli_inspect(error_root, error_key, capsys),
    ]
    for code, payload in cli_results:
        assert code == 0, f"a miss is an answer, not a failure; got exit {code}"
        assert payload == {"result": "miss"}, payload
    assert cli_results[0] == cli_results[1] == cli_results[2]


def test_caller_handling_identical_across_all_three_misses(isolated_env):
    """A caller's single isinstance(result, Miss) branch handles every case."""

    def caller(result):
        if isinstance(result, cache_manager.Miss):
            return "recompute"
        return "use-cached"

    evicted_root = isolated_env / "r-evicted"
    evicted_root.mkdir()
    k1 = _key("5")
    cache_manager.put(k1, _result(), repo_root=evicted_root)
    _evict_everything(evicted_root)

    never_root = isolated_env / "r-never"
    never_root.mkdir()

    error_root = isolated_env / "r-error"
    (error_root / ".hotdocs").mkdir(parents=True)
    (error_root / ".hotdocs" / "cache").write_text("garbage")

    outcomes = [
        caller(cache_manager.get(k1, repo_root=evicted_root)),
        caller(cache_manager.get(_key("6"), repo_root=never_root)),
        caller(cache_manager.get(_key("7"), repo_root=error_root)),
    ]
    assert outcomes == ["recompute", "recompute", "recompute"]