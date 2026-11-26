# hotdocs-criterion: sha256:c0d932190163260b55f9360458dad7b31e69f2ba04e85c2127588c9b09bb9816
import socket

import pytest

import cache_manager


def _closed_local_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _unreachable_urls():
    port = _closed_local_port()
    return [
        "http://127.0.0.1:" + str(port),
        "http://127.0.0.1:" + str(port) + "/cache",
        "http://cache-store.invalid:8080",
    ]


def _key(suffix, gate_type="license_scanner"):
    return cache_manager.CacheKey(
        spec_bundle_hash="sha256:" + ("a" * 63) + suffix,
        gate_inputs_hash="sha256:" + ("b" * 63) + suffix,
        gate_version=gate_type + "@4.0.3+9f2c41ab07de",
        model_pin="claude-sonnet-5",
    )


@pytest.mark.parametrize("url_index", [0, 1, 2])
@pytest.mark.parametrize(
    "key_args",
    [
        ("0", "license_scanner"),
        ("1", "secret_scanner"),
        ("2", "generator"),
        ("3", "llm_judge"),
    ],
)
def test_get_returns_miss_when_backing_store_unreachable(
    tmp_path, monkeypatch, url_index, key_args
):
    url = _unreachable_urls()[url_index]
    monkeypatch.setenv("VAR_CACHE_STORE_URL", url)
    monkeypatch.chdir(tmp_path)

    key = _key(*key_args)

    try:
        result = cache_manager.get(key, repo_root=tmp_path)
    except Exception as exc:  # pragma: no cover - failure path
        pytest.fail(
            "get raised " + type(exc).__name__ + " with unreachable store "
            + repr(url) + ": " + repr(exc)
        )

    assert result is not None
    assert isinstance(result, cache_manager.Miss)
    assert result == cache_manager.Miss()


def test_get_returns_miss_with_default_repo_root_when_store_unreachable(
    tmp_path, monkeypatch
):
    url = _unreachable_urls()[0]
    monkeypatch.setenv("VAR_CACHE_STORE_URL", url)
    monkeypatch.chdir(tmp_path)

    try:
        result = cache_manager.get(_key("9"))
    except Exception as exc:  # pragma: no cover - failure path
        pytest.fail("get raised " + type(exc).__name__ + ": " + repr(exc))

    assert isinstance(result, cache_manager.Miss)


def test_repeated_gets_keep_returning_miss_when_store_unreachable(
    tmp_path, monkeypatch
):
    url = _unreachable_urls()[0]
    monkeypatch.setenv("VAR_CACHE_STORE_URL", url)
    monkeypatch.chdir(tmp_path)

    key = _key("5")
    for _ in range(3):
        try:
            result = cache_manager.get(key, repo_root=tmp_path)
        except Exception as exc:  # pragma: no cover - failure path
            pytest.fail("get raised " + type(exc).__name__ + ": " + repr(exc))
        assert isinstance(result, cache_manager.Miss)