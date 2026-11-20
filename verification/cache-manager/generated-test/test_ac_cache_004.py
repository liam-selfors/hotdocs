# hotdocs-criterion: sha256:4c6c3ed298051302c982b4bf6e4e259a2bd4ccb7a390cec47fc530c97091830a
import socket

import pytest

import cache_manager


def _closed_local_port():
    """Return a TCP port on 127.0.0.1 that nothing is listening on."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _unreachable_urls():
    port = _closed_local_port()
    return [
        "http://127.0.0.1:" + str(port) + "/cache",
        "redis://127.0.0.1:" + str(port) + "/0",
        "http://hotdocs-cache-store.invalid:" + str(port) + "/",
    ]


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
            gate_version="generator@1.0.0",
            model_pin="anthropic:claude-sonnet-5",
        ),
        cache_manager.CacheKey(
            spec_bundle_hash="sha256:" + "0" * 64,
            gate_inputs_hash="sha256:" + "f" * 64,
            gate_version="secret_scanner@2.1.0",
            model_pin="none",
        ),
    ]


@pytest.mark.parametrize("url_index", [0, 1, 2])
def test_get_returns_miss_when_backing_store_unreachable(tmp_path, monkeypatch, url_index):
    url = _unreachable_urls()[url_index]
    monkeypatch.setenv("VAR_CACHE_STORE_URL", url)
    monkeypatch.chdir(tmp_path)

    for key in _keys():
        try:
            result = cache_manager.get(key, repo_root=tmp_path)
        except Exception as exc:  # pragma: no cover - failure path
            pytest.fail(
                "get raised " + type(exc).__name__ + " for unreachable store "
                + repr(url) + ": " + repr(exc)
            )
        assert result is not None
        assert isinstance(result, cache_manager.Miss)
        assert result == cache_manager.Miss()


def test_get_returns_miss_with_default_repo_root_when_store_unreachable(tmp_path, monkeypatch):
    url = _unreachable_urls()[0]
    monkeypatch.setenv("VAR_CACHE_STORE_URL", url)
    monkeypatch.chdir(tmp_path)

    key = _keys()[0]
    try:
        result = cache_manager.get(key)
    except Exception as exc:  # pragma: no cover - failure path
        pytest.fail("get raised " + type(exc).__name__ + ": " + repr(exc))
    assert isinstance(result, cache_manager.Miss)