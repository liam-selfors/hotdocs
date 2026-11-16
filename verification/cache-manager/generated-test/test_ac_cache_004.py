"""AC-CACHE-004 (Covers: R-CACHE-004).

Given the backing store at VAR-CACHE-STORE-URL is unreachable
When get is called with any key
Then it returns Miss rather than raising an exception
"""

import socket

import pytest

import cache_manager


def _closed_local_port():
    """Return a localhost TCP port that nothing is listening on."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    finally:
        s.close()
    return port


def _keys():
    return [
        cache_manager.CacheKey(
            spec_bundle_hash="sha256:" + "a" * 64,
            gate_inputs_hash="sha256:" + "b" * 64,
            gate_version="license_scanner@4.0.3+9f2c41ab07de",
            model_pin="claude-sonnet-5",
        ),
        cache_manager.CacheKey(
            spec_bundle_hash="sha256:" + "c" * 64,
            gate_inputs_hash="sha256:" + "d" * 64,
            gate_version="secret_scanner@1.2.0",
            model_pin="anthropic:claude-sonnet-5",
        ),
        cache_manager.CacheKey(
            spec_bundle_hash="sha256:" + "e" * 64,
            gate_inputs_hash="sha256:" + "f" * 64,
            gate_version="generator@0.1.0",
            model_pin="ollama:llama3.1:8b",
        ),
    ]


@pytest.mark.parametrize("scheme", ["http", "https", "redis"])
def test_get_returns_miss_when_backing_store_unreachable(
    tmp_path, monkeypatch, scheme
):
    port = _closed_local_port()
    url = f"{scheme}://127.0.0.1:{port}/"
    monkeypatch.setenv("VAR_CACHE_STORE_URL", url)
    monkeypatch.chdir(tmp_path)

    for key in _keys():
        try:
            result = cache_manager.get(key, repo_root=tmp_path)
        except Exception as exc:  # pragma: no cover - failure path
            pytest.fail(
                f"get raised {type(exc).__name__} with unreachable store "
                f"{url!r}: {exc!r}"
            )

        assert result is not None, "get must report a miss as a Miss instance, never None"
        assert isinstance(result, cache_manager.Miss), (
            f"expected a Miss for unreachable store {url!r}, got {result!r}"
        )
        assert result == cache_manager.Miss()


def test_get_returns_miss_when_backing_store_unreachable_default_repo_root(
    tmp_path, monkeypatch
):
    port = _closed_local_port()
    monkeypatch.setenv("VAR_CACHE_STORE_URL", f"http://127.0.0.1:{port}/")
    monkeypatch.chdir(tmp_path)

    key = _keys()[0]
    try:
        result = cache_manager.get(key)
    except Exception as exc:  # pragma: no cover - failure path
        pytest.fail(f"get raised {type(exc).__name__}: {exc!r}")

    assert isinstance(result, cache_manager.Miss)