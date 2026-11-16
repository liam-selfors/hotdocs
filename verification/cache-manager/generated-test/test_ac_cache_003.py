import copy
import threading

import pytest

import cache_manager


def _field(value, name):
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def _make_key(i):
    return cache_manager.CacheKey(
        spec_bundle_hash="sha256:" + ("%064x" % (0xA000 + i)),
        gate_inputs_hash="sha256:" + ("%064x" % (0xB000 + i)),
        gate_version="license_scanner@4.0.3+9f2c41ab07de",
        model_pin="claude-sonnet-5",
    )


def _make_payload(i):
    # A reasonably large payload so a partial or interleaved write would be
    # detectable as a mismatch rather than slipping through unnoticed.
    return {
        "component_id": "comp-example-%d" % i,
        "gate_version": "license_scanner@4.0.3+9f2c41ab07de",
        "similarity_score": 0.125,
        "blocked": False,
        "matches": [
            {
                "license": "MIT",
                "path": "gen/example/file_%03d.py" % n,
                "score": n / 1000.0,
                "snippet": ("x" * 200) + str(n),
            }
            for n in range(200)
        ],
    }


@pytest.fixture
def repo_root(tmp_path, monkeypatch):
    # Force the local fallback store under this temporary repo root.
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _concurrent_put(key, result_a, result_b, repo_root):
    barrier = threading.Barrier(2)
    errors = []

    def worker(result):
        try:
            barrier.wait(timeout=10)
            cache_manager.put(key, result, repo_root=repo_root)
        except Exception as exc:  # pragma: no cover - reported below
            errors.append(exc)

    threads = [
        threading.Thread(target=worker, args=(result_a,)),
        threading.Thread(target=worker, args=(result_b,)),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    for t in threads:
        assert not t.is_alive(), "a concurrent put did not complete"
    assert errors == [], "concurrent put raised: %r" % (errors,)


def test_concurrent_identical_puts_same_key_yield_uncorrupted_result(repo_root):
    stored_at = cache_manager.now_iso()

    for i in range(10):
        key = _make_key(i)
        payload = _make_payload(i)

        # Two independently constructed, identical results (G-CACHE-001's
        # precondition: deterministic gate, identical payloads).
        result_a = cache_manager.CachedResult(
            gate_type="license_scanner",
            payload=copy.deepcopy(payload),
            stored_at=stored_at,
        )
        result_b = cache_manager.CachedResult(
            gate_type="license_scanner",
            payload=copy.deepcopy(payload),
            stored_at=stored_at,
        )

        _concurrent_put(key, result_a, result_b, repo_root)

        got = cache_manager.get(key, repo_root=repo_root)
        assert not isinstance(got, cache_manager.Miss), (
            "get after concurrent puts returned a Miss for round %d" % i
        )

        got_gate_type = _field(got, "gate_type")
        got_payload = _field(got, "payload")
        got_stored_at = _field(got, "stored_at")

        assert got_gate_type == "license_scanner"
        assert got_gate_type == _field(result_a, "gate_type")
        assert got_gate_type == _field(result_b, "gate_type")

        # Equal to both payloads: no corruption, no partial write, no merge.
        assert got_payload == payload
        assert got_payload == _field(result_a, "payload")
        assert got_payload == _field(result_b, "payload")
        assert len(got_payload["matches"]) == 200

        assert got_stored_at == stored_at

        # A second get from a "different caller" sees the same authoritative
        # answer immediately.
        again = cache_manager.get(key, repo_root=repo_root)
        assert not isinstance(again, cache_manager.Miss)
        assert _field(again, "payload") == payload
        assert _field(again, "gate_type") == "license_scanner"


def test_concurrent_puts_do_not_corrupt_a_different_key(repo_root):
    stored_at = cache_manager.now_iso()

    other_key = _make_key(999)
    other_payload = _make_payload(999)
    cache_manager.put(
        other_key,
        cache_manager.CachedResult(
            gate_type="license_scanner",
            payload=copy.deepcopy(other_payload),
            stored_at=stored_at,
        ),
        repo_root=repo_root,
    )

    key = _make_key(500)
    payload = _make_payload(500)
    result_a = cache_manager.CachedResult(
        gate_type="license_scanner",
        payload=copy.deepcopy(payload),
        stored_at=stored_at,
    )
    result_b = cache_manager.CachedResult(
        gate_type="license_scanner",
        payload=copy.deepcopy(payload),
        stored_at=stored_at,
    )
    _concurrent_put(key, result_a, result_b, repo_root)

    got = cache_manager.get(key, repo_root=repo_root)
    assert not isinstance(got, cache_manager.Miss)
    assert _field(got, "payload") == payload
    assert _field(got, "gate_type") == "license_scanner"

    other = cache_manager.get(other_key, repo_root=repo_root)
    assert not isinstance(other, cache_manager.Miss)
    assert _field(other, "payload") == other_payload
    assert _field(other, "gate_type") == "license_scanner"
    assert _field(other, "stored_at") == stored_at