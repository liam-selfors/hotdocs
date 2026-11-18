# hotdocs-criterion: sha256:5c88050ddb651d4ee27c67e294631f736ea7b20dde8e2945c21946f04d872775
import copy
import threading

import pytest

import cache_manager


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


TRIALS = 20


def _make_key():
    return cache_manager.CacheKey(
        spec_bundle_hash="sha256:" + "a" * 64,
        gate_inputs_hash="sha256:" + "b" * 64,
        gate_version="generator@1.0.0",
        model_pin="claude-sonnet-5",
    )


def _payload(files):
    return {
        "component_id": "comp-example",
        "model": "anthropic:claude-sonnet-5",
        "prompt_version": "v1",
        "files": files,
    }


def _make_result(payload):
    return cache_manager.CachedResult(
        gate_type="generator",
        payload=payload,
        stored_at=cache_manager.now_iso(),
    )


@pytest.fixture(autouse=True)
def _local_store(monkeypatch):
    # Force the local `.hotdocs/cache/` fallback under each trial's repo_root.
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)


def test_concurrent_puts_same_key_never_merge_or_corrupt(tmp_path):
    payload_a = _payload({"a.py": "A"})
    payload_b = _payload({"b.py": "B"})
    expected_a = copy.deepcopy(payload_a)
    expected_b = copy.deepcopy(payload_b)

    for trial in range(TRIALS):
        repo_root = tmp_path / ("trial_" + str(trial))
        repo_root.mkdir()

        key = _make_key()
        result_a = _make_result(copy.deepcopy(payload_a))
        result_b = _make_result(copy.deepcopy(payload_b))

        barrier = threading.Barrier(2)
        errors = []

        def writer(result):
            try:
                barrier.wait(timeout=10)
                cache_manager.put(key, result, repo_root=repo_root)
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
            assert not t.is_alive(), "put thread did not finish in trial " + str(trial)

        assert errors == [], "put raised in trial " + str(trial) + ": " + repr(errors)

        got = cache_manager.get(key, repo_root=repo_root)
        assert not isinstance(got, cache_manager.Miss), (
            "entry missing after concurrent puts in trial " + str(trial)
        )

        assert field(got, "gate_type") == "generator"
        payload = field(got, "payload")
        assert isinstance(payload, dict), (
            "payload is not a dict in trial " + str(trial) + ": " + repr(payload)
        )

        files = payload.get("files")
        assert isinstance(files, dict), (
            "files missing or malformed in trial " + str(trial) + ": " + repr(payload)
        )
        assert not ("a.py" in files and "b.py" in files), (
            "payloads were merged in trial " + str(trial) + ": " + repr(payload)
        )

        assert payload == expected_a or payload == expected_b, (
            "payload is neither written payload exactly in trial "
            + str(trial)
            + ": "
            + repr(payload)
        )