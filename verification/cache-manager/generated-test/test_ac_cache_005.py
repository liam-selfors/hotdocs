import tempfile
from pathlib import Path

import cache_manager


def test_get_with_different_gate_version_is_miss_not_old_entry():
    with tempfile.TemporaryDirectory() as tmp:
        repo_root = Path(tmp)

        spec_bundle_hash = "sha256:" + "a" * 64
        gate_inputs_hash = "sha256:" + "b" * 64
        model_pin = "claude-sonnet-5"

        old_key = cache_manager.CacheKey(
            spec_bundle_hash=spec_bundle_hash,
            gate_inputs_hash=gate_inputs_hash,
            gate_version="license_scanner@1.0.0",
            model_pin=model_pin,
        )

        stored_result = cache_manager.CachedResult(
            gate_type="license_scanner",
            payload={
                "component_id": "comp-example",
                "gate_version": "license_scanner@1.0.0",
                "similarity_score": 0.0,
                "blocked": False,
                "matches": [],
            },
            stored_at=cache_manager.now_iso(),
        )

        cache_manager.put(old_key, stored_result, repo_root=repo_root)

        # Sanity check: the entry is retrievable under its own gate_version.
        hit = cache_manager.get(old_key, repo_root=repo_root)
        assert not isinstance(hit, cache_manager.Miss)

        new_key = cache_manager.CacheKey(
            spec_bundle_hash=spec_bundle_hash,
            gate_inputs_hash=gate_inputs_hash,
            gate_version="license_scanner@2.0.0",
            model_pin=model_pin,
        )

        result = cache_manager.get(new_key, repo_root=repo_root)

        assert isinstance(result, cache_manager.Miss)

        stored_gate_type = (
            result.get("gate_type")
            if isinstance(result, dict)
            else getattr(result, "gate_type", None)
        )
        assert stored_gate_type is None