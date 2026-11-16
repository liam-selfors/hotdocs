import threading

import pytest

import cache_manager


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _make_key(i):
    return cache_manager.CacheKey(
        spec_bundle_hash="sha256:" + ("%064x" % (0xA000 + i)),
        gate_inputs_hash="sha256:" + ("%064x" % (0xB000 + i)),
        gate_version="license_scanner@4.0.3+9f2c41ab07de",
        model_pin="claude-sonnet-5",
    )


def _make_payload(i):
    # A reasonably large payload, so a torn / partial write would be detectable.
    return {
        "component_id": "comp-example-%d" % i,
        "gate_version": "license_scanner@4.0.3+9f2c41ab07de",
        "similarity_score": 0.125,
        "blocked": False,
        "matches": [
            {
                "path": "gen/example/file_%04d.py" % j,
                "license": "MIT",
                "score": j / 1000.0,
                "snippet": "x" * 256,
            }
            for j in range(200)
        ],
    }


def _make_result(i, stored_at):
    return cache_manager.CachedResult(
        gate_type="license_scanner",
        payload=_make_payload(i),
        stored_at=stored_at,
    )


def _concurrent_put(key, result_a, result_b, repo_root):
    barrier = threading.Barrier(2)
    errors = []

    def worker(result):
        try:
            barrier.wait(timeout=10)
            cache_manager.put(key, result, repo_root=repo_root)
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    t1 = threading.Thread(target=worker, args=(result_a,))
    t2 = threading.Thread(target=worker, args=(result_b,))
    t1.start()
    t2.start()
    t1.join(timeout=60)
    t2.join(timeout=60)
    assert not t1.is_alive() and not t2.is_alive(), "concurrent put calls did not complete"
    assert errors == [], "concurrent put raised: %r" % (errors,)


def test_ac_cache_003_concurrent_identical_puts_yield_uncorrupted_result(tmp_path, monkeypatch):
    # Use the local fallback store under a fresh repo root.
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    monkeypatch.chdir(tmp_path)
    repo_root = tmp_path

    stored_at = cache_manager.now_iso()

    for i in range(10):
        key = _make_key(i)
        # Two independently constructed but identical results (the G-CACHE-001 precondition).
        result_a = _make_result(i, stored_at)
        result_b = _make_result(i, stored_at)
        expected_payload = _make_payload(i)
        assert field(result_a, "payload") == field(result_b, "payload") == expected_payload

        _concurrent_put(key, result_a, result_b, repo_root)

        got = cache_manager.get(key, repo_root=repo_root)
        assert not isinstance(got, cache_manager.Miss), (
            "get after two completed concurrent puts returned a Miss for key %d" % i
        )

        got_payload = field(got, "payload")
        assert got_payload == field(result_a, "payload")
        assert got_payload == field(result_b, "payload")
        assert got_payload == expected_payload
        assert field(got, "gate_type") == "license_scanner"
        assert field(got, "stored_at") == stored_at

        # A second, independent read must agree (no partially-written state observed).
        again = cache_manager.get(key, repo_root=repo_root)
        assert not isinstance(again, cache_manager.Miss)
        assert field(again, "payload") == expected_payload
        assert field(again, "gate_type") == "license_scanner"