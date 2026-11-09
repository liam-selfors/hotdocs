import os
import shutil
import tempfile

import cache_manager


def _field(value, name):
    return value.get(name) if isinstance(value, dict) else getattr(value, name, None)


def _build_key_as_caller_a(spec_bundle_hash, gate_inputs_hash, gate_version, model_pin):
    # Simulates one calling component constructing the cache key from its
    # own local variables, in the field order the data document lists.
    return cache_manager.CacheKey(
        spec_bundle_hash=spec_bundle_hash,
        gate_inputs_hash=gate_inputs_hash,
        gate_version=gate_version,
        model_pin=model_pin,
    )


def _build_key_as_caller_b(spec_bundle_hash, gate_inputs_hash, gate_version, model_pin):
    # Simulates a *different* calling component, independently assembling
    # the same four key components via its own kwargs dict and ordering.
    kwargs = {
        "model_pin": model_pin,
        "gate_version": gate_version,
        "gate_inputs_hash": gate_inputs_hash,
        "spec_bundle_hash": spec_bundle_hash,
    }
    return cache_manager.CacheKey(**kwargs)


def test_ac_cache_002_two_callers_produce_identical_cache_key():
    repo_root = tempfile.mkdtemp(prefix="cache-manager-ac-cache-002-")
    had_store_url = "VAR_CACHE_STORE_URL" in os.environ
    saved_store_url = os.environ.pop("VAR_CACHE_STORE_URL", None)

    try:
        spec_bundle_hash = "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        gate_inputs_hash = "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
        gate_version = "secret_scanner@1.0.0"
        model_pin = "claude-sonnet-5"

        key_from_caller_a = _build_key_as_caller_a(
            spec_bundle_hash, gate_inputs_hash, gate_version, model_pin
        )
        key_from_caller_b = _build_key_as_caller_b(
            spec_bundle_hash, gate_inputs_hash, gate_version, model_pin
        )

        first_payload = {
            "scope": "repo",
            "gate_version": gate_version,
            "flagged": False,
            "matches": [],
        }
        first_result = cache_manager.CachedResult(
            gate_type="secret_scanner",
            payload=first_payload,
            stored_at=cache_manager.now_iso(),
        )

        # Caller A puts under the key it independently computed.
        cache_manager.put(key_from_caller_a, first_result, repo_root=repo_root)

        stats_after_first_put = cache_manager.stats(repo_root=repo_root)
        entry_count_after_first_put = _field(stats_after_first_put, "entry_count")
        assert entry_count_after_first_put == 1

        second_payload = {
            "scope": "repo",
            "gate_version": gate_version,
            "flagged": True,
            "matches": [{"file": "secrets.txt", "rule": "aws_key"}],
        }
        second_result = cache_manager.CachedResult(
            gate_type="secret_scanner",
            payload=second_payload,
            stored_at=cache_manager.now_iso(),
        )

        # Caller B puts under the key *it* independently computed from the
        # same four components. If the two callers' serialized keys were
        # not byte-identical, this would land under a distinct entry.
        cache_manager.put(key_from_caller_b, second_result, repo_root=repo_root)

        stats_after_second_put = cache_manager.stats(repo_root=repo_root)
        entry_count_after_second_put = _field(stats_after_second_put, "entry_count")
        assert entry_count_after_second_put == 1

        # A get() through either caller's own key must see the same,
        # single stored entry (last-write-wins over the second put).
        result_seen_by_a = cache_manager.get(key_from_caller_a, repo_root=repo_root)
        result_seen_by_b = cache_manager.get(key_from_caller_b, repo_root=repo_root)

        assert not isinstance(result_seen_by_a, cache_manager.Miss)
        assert not isinstance(result_seen_by_b, cache_manager.Miss)

        payload_seen_by_a = _field(result_seen_by_a, "payload")
        payload_seen_by_b = _field(result_seen_by_b, "payload")
        gate_type_seen_by_a = _field(result_seen_by_a, "gate_type")
        gate_type_seen_by_b = _field(result_seen_by_b, "gate_type")

        assert payload_seen_by_a == second_payload
        assert payload_seen_by_b == second_payload
        assert payload_seen_by_a == payload_seen_by_b
        assert gate_type_seen_by_a == "secret_scanner"
        assert gate_type_seen_by_b == "secret_scanner"
    finally:
        if had_store_url:
            os.environ["VAR_CACHE_STORE_URL"] = saved_store_url
        shutil.rmtree(repo_root, ignore_errors=True)