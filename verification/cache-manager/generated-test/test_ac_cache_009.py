import os
import shutil
import tempfile
import threading

import cache_manager


def _field(obj, name):
    return obj.get(name) if isinstance(obj, dict) else getattr(obj, name, None)


def test_concurrent_put_same_key_never_corrupts_or_merges():
    saved_store_url = os.environ.pop("VAR_CACHE_STORE_URL", None)
    try:
        payload_a = {
            "component_id": "comp-example",
            "model": "anthropic:claude-sonnet-5",
            "prompt_version": "v1",
            "files": {"a.py": "A"},
        }
        payload_b = {
            "component_id": "comp-example",
            "model": "anthropic:claude-sonnet-5",
            "prompt_version": "v1",
            "files": {"b.py": "B"},
        }

        for trial in range(20):
            repo_root = tempfile.mkdtemp(prefix="cache-mgr-trial-")
            try:
                cache_key = cache_manager.CacheKey(
                    spec_bundle_hash="sha256:" + "a" * 64,
                    gate_inputs_hash="sha256:" + "b" * 64,
                    gate_version="generator@1.0.0",
                    model_pin="claude-sonnet-5",
                )
                result_a = cache_manager.CachedResult(
                    gate_type="generator",
                    payload=payload_a,
                    stored_at=cache_manager.now_iso(),
                )
                result_b = cache_manager.CachedResult(
                    gate_type="generator",
                    payload=payload_b,
                    stored_at=cache_manager.now_iso(),
                )

                barrier = threading.Barrier(2)
                errors = []

                def _put(result):
                    try:
                        barrier.wait(timeout=5)
                        cache_manager.put(cache_key, result, repo_root=repo_root)
                    except Exception as exc:
                        errors.append(exc)

                t1 = threading.Thread(target=_put, args=(result_a,))
                t2 = threading.Thread(target=_put, args=(result_b,))
                t1.start()
                t2.start()
                t1.join(timeout=10)
                t2.join(timeout=10)

                assert not errors, "trial {}: put raised unexpectedly: {}".format(
                    trial, errors
                )

                fetched = cache_manager.get(cache_key, repo_root=repo_root)
                assert not isinstance(fetched, cache_manager.Miss), (
                    "trial {}: expected a hit after concurrent puts, got a miss".format(
                        trial
                    )
                )

                fetched_payload = _field(fetched, "payload")
                assert fetched_payload is not None, (
                    "trial {}: hit had no payload (missing/truncated entry)".format(
                        trial
                    )
                )

                files = (
                    fetched_payload.get("files")
                    if isinstance(fetched_payload, dict)
                    else None
                )
                assert files is not None, (
                    "trial {}: payload missing 'files' key".format(trial)
                )
                assert set(files.keys()) in ({"a.py"}, {"b.py"}), (
                    "trial {}: files keys {} indicate a merged or corrupted "
                    "entry".format(trial, set(files.keys()))
                )

                assert fetched_payload == payload_a or fetched_payload == payload_b, (
                    "trial {}: fetched payload {} does not exactly match either "
                    "original payload".format(trial, fetched_payload)
                )
            finally:
                shutil.rmtree(repo_root, ignore_errors=True)
    finally:
        if saved_store_url is not None:
            os.environ["VAR_CACHE_STORE_URL"] = saved_store_url