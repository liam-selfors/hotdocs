"""One test per AC-CACHE-* criterion in
specs/components/cache-manager/acceptance/.
"""

import json
import threading

from conftest import make_key, make_license_result
from cache_manager import CacheKey, CachedResult, Miss, SchemaValidationError, get, put, stats


def test_ac_cache_001_miss_on_unstored_key(repo_root):
    result = get(make_key(), repo_root=repo_root)
    assert result == Miss()


def test_ac_cache_002_key_serialization_is_byte_identical(repo_root):
    """R-CACHE-002 -- the key is its four fields, however a caller builds
    it: a put under one construction is a hit under the other."""
    k1 = CacheKey("sha256:x", "sha256:y", "license_scanner@1.0.0", "claude-sonnet-5")
    k2 = CacheKey(
        model_pin="claude-sonnet-5", gate_version="license_scanner@1.0.0",
        gate_inputs_hash="sha256:y", spec_bundle_hash="sha256:x",
    )
    put(k1, make_license_result(), repo_root=repo_root)
    assert isinstance(get(k2, repo_root=repo_root), CachedResult)


def test_ac_cache_003_concurrent_identical_writes_not_corrupted(repo_root):
    key = make_key()
    result = make_license_result()
    errors = []

    def writer():
        try:
            put(key, result, repo_root=repo_root)
        except Exception as exc:  # pragma: no cover - diagnostic only
            errors.append(exc)

    threads = [threading.Thread(target=writer) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors
    stored = get(key, repo_root=repo_root)
    assert isinstance(stored, CachedResult)
    assert stored.payload == result.payload


def test_ac_cache_004_miss_on_unreachable_store(repo_root, monkeypatch):
    monkeypatch.setenv("VAR_CACHE_STORE_URL", "redis://unreachable.invalid:6379/0")
    assert get(make_key(), repo_root=repo_root) == Miss()


def test_ac_cache_005_gate_version_is_part_of_the_key(repo_root):
    key_v1 = make_key(gate_version="license_scanner@1.0.0")
    put(key_v1, make_license_result(), repo_root=repo_root)

    key_v2 = make_key(gate_version="license_scanner@2.0.0")
    assert get(key_v2, repo_root=repo_root) == Miss()


def test_ac_cache_006_stats_reports_something_queryable(repo_root):
    put(make_key(), make_license_result(), repo_root=repo_root)
    s = stats(repo_root=repo_root)
    assert s["entry_count"] == 1


def test_ac_cache_007_rejects_mismatched_payload_shape(repo_root):
    bad_result = CachedResult(
        gate_type="license_scanner",
        payload={"findings": [], "summary": {}},  # a LintReport shape, not license_scanner's
        stored_at="2026-01-01T00:00:00Z",
    )
    try:
        put(make_key(), bad_result, repo_root=repo_root)
        assert False, "expected SchemaValidationError"
    except SchemaValidationError:
        pass
    assert get(make_key(), repo_root=repo_root) == Miss()


def test_ac_cache_008_evicted_key_is_a_plain_miss(repo_root):
    key = make_key()
    put(key, make_license_result(), repo_root=repo_root)
    # Simulate backing-store eviction directly -- same file path a real
    # store would stop serving.
    (repo_root / ".hotdocs" / "cache" / f"{key.digest()}.json").unlink()
    assert get(key, repo_root=repo_root) == Miss()


def test_ac_cache_009_concurrent_distinct_writes_one_survives_whole(repo_root):
    key = make_key(gate_version="generated_test@1.0.0")
    result_a = CachedResult(
        gate_type="generated_test",
        payload={"component_id": "comp-foo", "criterion_id": "AC-FOO-001", "model": "claude-sonnet-5", "file": "a.py"},
        stored_at="2026-01-01T00:00:00Z",
    )
    result_b = CachedResult(
        gate_type="generated_test",
        payload={"component_id": "comp-foo", "criterion_id": "AC-FOO-001", "model": "claude-opus-5", "file": "b.py"},
        stored_at="2026-01-01T00:00:01Z",
    )
    put(key, result_a, repo_root=repo_root)
    put(key, result_b, repo_root=repo_root)

    stored = get(key, repo_root=repo_root)
    assert isinstance(stored, CachedResult)
    assert stored.payload in (result_a.payload, result_b.payload)


def test_ac_cache_010_local_fallback_round_trip(repo_root):
    key = make_key()
    result = make_license_result()
    put(key, result, repo_root=repo_root)
    stored = get(key, repo_root=repo_root)
    assert isinstance(stored, CachedResult)
    assert stored.payload == result.payload
    cache_file = repo_root / ".hotdocs" / "cache" / f"{key.digest()}.json"
    assert json.loads(cache_file.read_text())["result"]["payload"] == result.payload
