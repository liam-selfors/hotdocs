import cache_manager

from pathlib import Path


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


SPEC_BUNDLE_HASH = "sha256:" + "a" * 64
GATE_INPUTS_HASH = "sha256:" + "b" * 64
MODEL_PIN = "claude-sonnet-5"
OLD_GATE_VERSION = "license_scanner@1.0.0"
NEW_GATE_VERSION = "license_scanner@2.0.0"


def _key(gate_version):
    return cache_manager.CacheKey(
        spec_bundle_hash=SPEC_BUNDLE_HASH,
        gate_inputs_hash=GATE_INPUTS_HASH,
        gate_version=gate_version,
        model_pin=MODEL_PIN,
    )


def _result():
    return cache_manager.CachedResult(
        gate_type="license_scanner",
        payload={
            "component_id": "comp-example",
            "gate_version": OLD_GATE_VERSION,
            "similarity_score": 0.0,
            "blocked": False,
            "matches": [],
        },
        stored_at=cache_manager.now_iso(),
    )


def test_ac_cache_005_gate_version_is_part_of_lookup_key(tmp_path, monkeypatch):
    # Force the local fallback store under a fresh, isolated repo root.
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    monkeypatch.chdir(tmp_path)
    repo_root = Path(tmp_path)

    old_key = _key(OLD_GATE_VERSION)
    cache_manager.put(old_key, _result(), repo_root=repo_root)

    # Sanity: the entry really is stored and retrievable under its own key.
    hit = cache_manager.get(old_key, repo_root=repo_root)
    assert not isinstance(hit, cache_manager.Miss), (
        "precondition failed: entry stored under the old gate_version was not retrievable"
    )
    assert field(hit, "gate_type") == "license_scanner"

    # Same spec_bundle_hash / gate_inputs_hash / model_pin, different gate_version.
    new_key = _key(NEW_GATE_VERSION)
    result = cache_manager.get(new_key, repo_root=repo_root)

    assert result is not None
    assert isinstance(result, cache_manager.Miss), (
        "get with gate_version %r returned an entry stored under %r"
        % (NEW_GATE_VERSION, OLD_GATE_VERSION)
    )
    assert result == cache_manager.Miss()