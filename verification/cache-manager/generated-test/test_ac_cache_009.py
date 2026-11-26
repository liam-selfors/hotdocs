# hotdocs-criterion: sha256:827c28c7956ace284d31a641e8f8caba55165ceef39e820144c73325de5c86ee
import copy
import threading

import cache_manager


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


GATE_VERSION = "generator@1.0.0"

BASE = {
    "component_id": "comp-widget",
    "model": "anthropic:claude-sonnet-5",
    "prompt_version": "p1",
}

PAYLOAD_A = dict(BASE, files={"a.py": "A"})
PAYLOAD_B = dict(BASE, files={"b.py": "B"})


def make_key():
    return cache_manager.CacheKey(
        spec_bundle_hash="sha256:" + "1" * 64,
        gate_inputs_hash="sha256:" + "2" * 64,
        gate_version=GATE_VERSION,
        model_pin="claude-sonnet-5",
    )


def make_result(payload):
    return cache_manager.CachedResult(
        gate_type="generator",
        payload=copy.deepcopy(payload),
        stored_at=cache_manager.now_iso(),
    )


def test_ac_cache_009_concurrent_puts_never_merge_or_corrupt(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)

    for trial in range(20):
        repo_root = tmp_path / ("trial_" + str(trial))
        repo_root.mkdir()

        key = make_key()
        result_a = make_result(PAYLOAD_A)
        result_b = make_result(PAYLOAD_B)

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

        got = cache_manager.get(make_key(), repo_root=repo_root)
        assert not isinstance(got, cache_manager.Miss), (
            "entry missing after concurrent puts in trial " + str(trial)
        )

        assert field(got, "gate_type") == "generator"
        payload = field(got, "payload")
        assert payload == PAYLOAD_A or payload == PAYLOAD_B, (
            "trial " + str(trial) + " returned corrupted/merged payload: " + repr(payload)
        )

        files = payload["files"] if isinstance(payload, dict) else getattr(payload, "files")
        assert not ("a.py" in files and "b.py" in files), (
            "trial " + str(trial) + " merged files from both writes: " + repr(files)
        )