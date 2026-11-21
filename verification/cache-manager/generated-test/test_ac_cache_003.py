# hotdocs-criterion: sha256:cc0618940afc954438e222e2fb6bb90dcadb387c4ff18858e4b4f95ab3597f8a
import threading

import pytest

import cache_manager


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _make_key(suffix):
    return cache_manager.CacheKey(
        spec_bundle_hash="sha256:" + ("a" * 63) + suffix,
        gate_inputs_hash="sha256:" + ("b" * 63) + suffix,
        gate_version="license_scanner@4.0.3+9f2c41ab07de",
        model_pin="claude-sonnet-5",
    )


def _make_payload():
    return {
        "component_id": "comp-example",
        "gate_version": "license_scanner@4.0.3+9f2c41ab07de",
        "similarity_score": 0.125,
        "blocked": False,
        "matches": [
            {"path": "src/a.py", "license": "MIT", "score": 0.125},
            {"path": "src/b.py", "license": "Apache-2.0", "score": 0.0625},
        ],
    }


def _make_result(stored_at):
    return cache_manager.CachedResult(
        gate_type="license_scanner",
        payload=_make_payload(),
        stored_at=stored_at,
    )


def _run_concurrent_puts(key, results, repo_root):
    barrier = threading.Barrier(len(results))
    errors = []

    def worker(result):
        try:
            barrier.wait(timeout=10)
            cache_manager.put(key, result, repo_root=repo_root)
        except BaseException as exc:  # pragma: no cover - reported below
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(r,)) for r in results]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    for t in threads:
        assert not t.is_alive(), "a concurrent put did not complete"
    assert errors == [], "concurrent put raised: " + repr(errors)


@pytest.fixture
def repo_root(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_two_concurrent_identical_puts_yield_uncorrupted_entry(repo_root):
    stored_at = cache_manager.now_iso()
    key = _make_key("0")
    first = _make_result(stored_at)
    second = _make_result(stored_at)
    assert field(first, "payload") == field(second, "payload")

    _run_concurrent_puts(key, [first, second], repo_root)

    got = cache_manager.get(key, repo_root=repo_root)
    assert not isinstance(got, cache_manager.Miss)
    assert got is not None
    assert field(got, "gate_type") == "license_scanner"
    assert field(got, "payload") == field(first, "payload")
    assert field(got, "payload") == field(second, "payload")
    assert field(got, "payload") == _make_payload()
    assert field(got, "stored_at") == stored_at


def test_repeated_concurrent_identical_puts_never_corrupt(repo_root):
    stored_at = cache_manager.now_iso()
    for i in range(10):
        key = _make_key(str(i))
        results = [_make_result(stored_at), _make_result(stored_at)]
        _run_concurrent_puts(key, results, repo_root)

        got = cache_manager.get(key, repo_root=repo_root)
        assert not isinstance(got, cache_manager.Miss), "iteration " + repr(i)
        assert field(got, "gate_type") == "license_scanner"
        assert field(got, "payload") == _make_payload(), "iteration " + repr(i)
        assert field(got, "stored_at") == stored_at

        # A second read is still the same, complete entry.
        again = cache_manager.get(key, repo_root=repo_root)
        assert not isinstance(again, cache_manager.Miss)
        assert field(again, "payload") == _make_payload()


def test_concurrent_identical_puts_do_not_disturb_other_entry(repo_root):
    stored_at = cache_manager.now_iso()
    other_key = _make_key("x")
    other_payload = dict(_make_payload())
    other_payload["component_id"] = "comp-other"
    other_result = cache_manager.CachedResult(
        gate_type="license_scanner",
        payload=other_payload,
        stored_at=stored_at,
    )
    cache_manager.put(other_key, other_result, repo_root=repo_root)

    key = _make_key("y")
    _run_concurrent_puts(
        key, [_make_result(stored_at), _make_result(stored_at)], repo_root
    )

    got = cache_manager.get(key, repo_root=repo_root)
    assert not isinstance(got, cache_manager.Miss)
    assert field(got, "payload") == _make_payload()

    got_other = cache_manager.get(other_key, repo_root=repo_root)
    assert not isinstance(got_other, cache_manager.Miss)
    assert field(got_other, "payload") == other_payload
    assert field(got_other, "gate_type") == "license_scanner"