# hotdocs-criterion: sha256:9aa1aa7386097eb68a57598fa8b49ce9374dbed454a0db1761eff7ee48e288ca
"""AC-CACHE-005: gate_version is part of the lookup key itself (R-CACHE-005)."""

import cache_manager


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
            "component_id": "comp-foo",
            "gate_version": OLD_GATE_VERSION,
            "similarity_score": 0.0,
            "blocked": False,
            "matches": [],
        },
        stored_at=cache_manager.now_iso(),
    )


def test_get_with_different_gate_version_returns_miss(tmp_path, monkeypatch):
    # Force the local fallback store under a fresh repo_root.
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    monkeypatch.chdir(tmp_path)

    stored = _result()
    cache_manager.put(_key(OLD_GATE_VERSION), stored, repo_root=tmp_path)

    # Sanity: the entry is retrievable under its own gate_version.
    hit = cache_manager.get(_key(OLD_GATE_VERSION), repo_root=tmp_path)
    assert not isinstance(hit, cache_manager.Miss)
    assert field(hit, "gate_type") == "license_scanner"

    # Same spec_bundle_hash / gate_inputs_hash / model_pin, new gate_version.
    result = cache_manager.get(_key(NEW_GATE_VERSION), repo_root=tmp_path)
    assert result is not None
    assert isinstance(result, cache_manager.Miss)
    assert result == cache_manager.Miss()


def test_old_entry_not_returned_under_new_gate_version_even_after_repeat(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    monkeypatch.chdir(tmp_path)

    cache_manager.put(_key(OLD_GATE_VERSION), _result(), repo_root=tmp_path)

    for _ in range(2):
        result = cache_manager.get(_key(NEW_GATE_VERSION), repo_root=tmp_path)
        assert isinstance(result, cache_manager.Miss)