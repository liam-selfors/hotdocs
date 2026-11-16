import threading

import pytest

import cache_manager


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _make_key():
    return cache_manager.CacheKey(
        spec_bundle_hash="sha256:" + "1" * 64,
        gate_inputs_hash="sha256:" + "2" * 64,
        gate_version="generator@1.0.0",
        model_pin="claude-sonnet-5",
    )


def _payload(files):
    return {
        "component_id": "comp-example",
        "model": "anthropic:claude-sonnet-5",
        "prompt_version": "v1",
        "files": dict(files),
    }


def _result(payload):
    return cache_manager.CachedResult(
        gate_type="generator",
        payload=payload,
        stored_at=cache_manager.now_iso(),
    )


def test_ac_cache_009_concurrent_puts_never_merge_or_corrupt(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)

    payload_a = _payload({"a.py": "A"})
    payload_b = _payload({"b.py": "B"})

    for trial in range(20):
        repo_root = tmp_path / f"trial_{trial}"
        repo_root.mkdir()

        key = _make_key()
        result_a = _result(_payload({"a.py": "A"}))
        result_b = _result(_payload({"b.py": "B"}))

        barrier = threading.Barrier(2)
        errors = []

        def writer(res):
            try:
                barrier.wait(timeout=10)
                cache_manager.put(key, res, repo_root=repo_root)
            except BaseException as exc:  # noqa: BLE001
                errors.append(exc)

        threads = [
            threading.Thread(target=writer, args=(result_a,)),
            threading.Thread(target=writer, args=(result_b,)),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)
        for t in threads:
            assert not t.is_alive(), f"trial {trial}: put thread hung"

        assert errors == [], f"trial {trial}: put raised {errors!r}"

        got = cache_manager.get(_make_key(), repo_root=repo_root)
        assert not isinstance(got, cache_manager.Miss), (
            f"trial {trial}: get returned Miss after two successful puts"
        )
        assert got is not None

        assert field(got, "gate_type") == "generator"
        payload = field(got, "payload")
        payload = dict(payload) if not isinstance(payload, dict) else payload

        assert payload == payload_a or payload == payload_b, (
            f"trial {trial}: payload {payload!r} matches neither written payload"
        )

        files = payload["files"]
        assert not ("a.py" in files and "b.py" in files), (
            f"trial {trial}: payload files were merged: {files!r}"
        )