import socket

import pytest

import cache_manager


def _unreachable_store_url():
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]
    probe.close()
    # Nothing listens on this port once probe is closed, so any connection
    # attempt against it simulates an unreachable backing store.
    return f"http://127.0.0.1:{port}/cache"


def test_get_returns_miss_when_backing_store_unreachable(tmp_path, monkeypatch):
    monkeypatch.setenv("VAR_CACHE_STORE_URL", _unreachable_store_url())

    key = cache_manager.CacheKey(
        spec_bundle_hash="sha256:" + "a" * 64,
        gate_inputs_hash="sha256:" + "b" * 64,
        gate_version="license_scanner@1.0.0",
        model_pin="claude-sonnet-5",
    )

    try:
        result = cache_manager.get(key, repo_root=tmp_path)
    except Exception as exc:  # noqa: BLE001 - this is exactly what AC-CACHE-004 forbids
        pytest.fail(
            f"get() raised {exc!r} instead of returning a Miss for an "
            "unreachable backing store"
        )

    assert isinstance(result, cache_manager.Miss)