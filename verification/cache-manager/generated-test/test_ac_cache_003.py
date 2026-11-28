# hotdocs-criterion: sha256:382b430b0165d36044624919799e896cc0aa6edd979285629c9d6751af35eed6
"""AC-CACHE-003: concurrent identical puts for the same key leave an
uncorrupted entry that a later get returns, equal to both payloads
(R-CACHE-003, G-CACHE-001)."""

import copy
import threading

import pytest

import cache_manager


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _make_key(i):
    return cache_manager.CacheKey(
        spec_bundle_hash="sha256:" + ("a" * 63) + str(i % 10),
        gate_inputs_hash="sha256:" + ("b" * 63) + str(i % 10),
        gate_version="license_scanner@4.0.3+9f2c41ab07de",
        model_pin="claude-sonnet-5",
    )


def _make_payload(i):
    return {
        "component_id": "comp-cache-manager",
        "gate_version": "license_scanner@4.0.3+9f2c41ab07de",
        "similarity_score": 0.125,
        "blocked": False,
        "matches": [
            {"file": "gen/cache-manager/x.py", "score": 0.1, "index": i},
            {"file": "gen/cache-manager/y.py", "score": 0.05, "note": "n" * 2048},
        ],
    }


def _make_result(payload, stored_at):
    return cache_manager.CachedResult(
        gate_type="license_scanner",
        payload=copy.deepcopy(payload),
        stored_at=stored_at,
    )


def _concurrent_put(key, results, repo_root, writers):
    barrier = threading.Barrier(writers)
    errors = []

    def worker(res):
        try:
            barrier.wait(timeout=10)
            cache_manager.put(key, res, repo_root=repo_root)
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(r,)) for r in results]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    for t in threads:
        assert not t.is_alive(), "a concurrent put did not complete"
    return errors


@pytest.mark.parametrize("iteration", range(10))
def test_concurrent_identical_puts_leave_uncorrupted_entry(tmp_path, monkeypatch, iteration):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    monkeypatch.chdir(tmp_path)
    repo_root = tmp_path

    key = _make_key(iteration)
    payload = _make_payload(iteration)
    stored_at = cache_manager.now_iso()

    # Two independent but identical result objects, one per writer.
    first = _make_result(payload, stored_at)
    second = _make_result(payload, stored_at)

    errors = _concurrent_put(key, [first, second], repo_root, writers=2)
    assert errors == [], "concurrent put raised: " + repr(errors)

    got = cache_manager.get(key, repo_root=repo_root)
    assert not isinstance(got, cache_manager.Miss), "expected a hit after concurrent puts"

    assert field(got, "gate_type") == "license_scanner"
    assert field(got, "payload") == field(first, "payload")
    assert field(got, "payload") == field(second, "payload")
    assert field(got, "payload") == payload
    assert field(got, "stored_at") == stored_at

    # A second, independent get agrees: the entry is stable, not partial.
    again = cache_manager.get(key, repo_root=repo_root)
    assert not isinstance(again, cache_manager.Miss)
    assert field(again, "payload") == payload
    assert field(again, "gate_type") == "license_scanner"


def test_many_concurrent_identical_puts_same_key(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    monkeypatch.chdir(tmp_path)
    repo_root = tmp_path

    key = _make_key(42)
    payload = _make_payload(42)
    stored_at = cache_manager.now_iso()
    results = [_make_result(payload, stored_at) for _ in range(8)]

    errors = _concurrent_put(key, results, repo_root, writers=len(results))
    assert errors == [], "concurrent put raised: " + repr(errors)

    got = cache_manager.get(key, repo_root=repo_root)
    assert not isinstance(got, cache_manager.Miss), "expected a hit after concurrent puts"
    assert field(got, "gate_type") == "license_scanner"
    assert field(got, "stored_at") == stored_at
    for r in results:
        assert field(got, "payload") == field(r, "payload")

    # Exactly one entry exists for the key: no duplicate or merged fragments.
    assert field(cache_manager.stats(repo_root=repo_root), "entry_count") == 1