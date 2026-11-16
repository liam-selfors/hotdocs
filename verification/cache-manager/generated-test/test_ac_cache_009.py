import copy
import threading
from pathlib import Path

import pytest

import cache_manager


def _field(value, name):
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


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


def _make_result(payload):
    return cache_manager.CachedResult(
        gate_type="generator",
        payload=copy.deepcopy(payload),
        stored_at=cache_manager.now_iso(),
    )


def _run_trial(repo_root: Path):
    payload_a = _payload({"a.py": "A"})
    payload_b = _payload({"b.py": "B"})
    key_a = _make_key()
    key_b = _make_key()
    result_a = _make_result(payload_a)
    result_b = _make_result(payload_b)

    barrier = threading.Barrier(2)
    errors = []
    errors_lock = threading.Lock()

    def writer(key, result):
        try:
            barrier.wait(timeout=10)
            cache_manager.put(key, result, repo_root=repo_root)
        except BaseException as exc:  # noqa: BLE001
            with errors_lock:
                errors.append(exc)

    t1 = threading.Thread(target=writer, args=(key_a, result_a))
    t2 = threading.Thread(target=writer, args=(key_b, result_b))
    t1.start()
    t2.start()
    t1.join(timeout=30)
    t2.join(timeout=30)

    assert not t1.is_alive() and not t2.is_alive(), "concurrent put calls did not finish"
    assert errors == [], f"concurrent put raised: {errors!r}"

    got = cache_manager.get(_make_key(), repo_root=repo_root)
    return got, payload_a, payload_b


def test_ac_cache_009_concurrent_puts_never_merge_or_corrupt(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)

    for trial in range(20):
        repo_root = tmp_path / f"trial_{trial}"
        repo_root.mkdir()

        got, payload_a, payload_b = _run_trial(repo_root)

        assert not isinstance(got, cache_manager.Miss), (
            f"trial {trial}: get returned Miss after two concurrent puts"
        )
        assert got is not None, f"trial {trial}: get returned None"

        gate_type = _field(got, "gate_type")
        assert gate_type == "generator", (
            f"trial {trial}: unexpected gate_type {gate_type!r}"
        )

        payload = _field(got, "payload")
        assert isinstance(payload, dict), (
            f"trial {trial}: payload is not a dict: {payload!r}"
        )

        files = payload.get("files")
        assert isinstance(files, dict), (
            f"trial {trial}: payload files missing or not a dict: {files!r}"
        )
        assert not ("a.py" in files and "b.py" in files), (
            f"trial {trial}: payload merged both writes: {files!r}"
        )

        for required in ("component_id", "model", "prompt_version", "files"):
            assert required in payload, (
                f"trial {trial}: payload missing required key {required!r}: {payload!r}"
            )

        assert payload == payload_a or payload == payload_b, (
            f"trial {trial}: payload matches neither written payload: {payload!r}"
        )

        stored_at = _field(got, "stored_at")
        assert isinstance(stored_at, str) and stored_at, (
            f"trial {trial}: stored_at missing or truncated: {stored_at!r}"
        )