import tempfile
import threading
from pathlib import Path

import cache_manager


def _make_key():
    return cache_manager.CacheKey(
        spec_bundle_hash="sha256:" + "a" * 64,
        gate_inputs_hash="sha256:" + "b" * 64,
        gate_version="license_scanner@1.0.0",
        model_pin="claude-sonnet-5",
    )


def _make_payload():
    return {
        "component_id": "comp-cache-manager",
        "gate_version": "license_scanner@1.0.0",
        "similarity_score": 0.12,
        "blocked": False,
        "matches": [],
    }


def test_concurrent_put_identical_payloads_no_corruption():
    with tempfile.TemporaryDirectory() as tmp:
        repo_root = Path(tmp)
        key = _make_key()
        stored_at = cache_manager.now_iso()
        payload = _make_payload()

        errors = []
        barrier = threading.Barrier(2)

        def do_put():
            try:
                barrier.wait(timeout=5)
                result = cache_manager.CachedResult(
                    gate_type="license_scanner",
                    payload=dict(payload),
                    stored_at=stored_at,
                )
                cache_manager.put(key, result, repo_root=repo_root)
            except Exception as exc:
                errors.append(exc)

        t1 = threading.Thread(target=do_put)
        t2 = threading.Thread(target=do_put)
        t1.start()
        t2.start()
        t1.join(timeout=10)
        t2.join(timeout=10)

        assert not errors, "put raised unexpectedly: {}".format(errors)

        fetched = cache_manager.get(key, repo_root=repo_root)
        assert not isinstance(fetched, cache_manager.Miss)

        gate_type = (
            fetched.get("gate_type")
            if isinstance(fetched, dict)
            else getattr(fetched, "gate_type", None)
        )
        fetched_payload = (
            fetched.get("payload")
            if isinstance(fetched, dict)
            else getattr(fetched, "payload", None)
        )
        fetched_stored_at = (
            fetched.get("stored_at")
            if isinstance(fetched, dict)
            else getattr(fetched, "stored_at", None)
        )

        assert gate_type == "license_scanner"
        assert fetched_payload == payload
        assert fetched_stored_at == stored_at

        cache_stats = cache_manager.stats(repo_root=repo_root)
        entry_count = (
            cache_stats.get("entry_count")
            if isinstance(cache_stats, dict)
            else getattr(cache_stats, "entry_count", None)
        )
        assert entry_count == 1