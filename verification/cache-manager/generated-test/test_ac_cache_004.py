# hotdocs-criterion: sha256:762e8b3f7f4fea01e84277a11f9f61e426dec411a6332a75d570825bf2451807
import socket

import pytest

import cache_manager


def _closed_local_port():
    """Return a localhost TCP port that nothing is listening on."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _unreachable_urls():
    port = _closed_local_port()
    return [
        "http://127.0.0.1:%d" % port,
        "http://127.0.0.1:%d/cache" % port,
        "redis://127.0.0.1:%d/0" % port,
        "tcp://127.0.0.1:%d" % port,
    ]


def _make_key(suffix):
    return cache_manager.CacheKey(
        spec_bundle_hash="sha256:" + ("a" * 63) + suffix,
        gate_inputs_hash="sha256:" + ("b" * 63) + suffix,
        gate_version="license_scanner@4.0.3+9f2c41ab07de",
        model_pin="claude-sonnet-5",
    )


def _assert_miss(result):
    assert result is not None, "get must report a miss with a Miss instance, never None"
    assert isinstance(result, cache_manager.Miss), (
        "expected a Miss on an unreachable backing store, got %r" % (result,)
    )


@pytest.mark.parametrize("url_index", range(4))
@pytest.mark.parametrize("key_suffix", ["0", "1", "f"])
def test_get_returns_miss_when_backing_store_unreachable(
    tmp_path, monkeypatch, url_index, key_suffix
):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)

    url = _unreachable_urls()[url_index]
    monkeypatch.setenv("VAR_CACHE_STORE_URL", url)

    key = _make_key(key_suffix)

    try:
        result = cache_manager.get(key, repo_root=repo_root)
    except Exception as exc:  # pragma: no cover - failure path
        pytest.fail(
            "get raised %s(%r) on an unreachable backing store (%s); "
            "R-CACHE-004 requires it to return Miss instead"
            % (type(exc).__name__, exc, url)
        )

    _assert_miss(result)


def test_get_returns_miss_when_backing_store_unreachable_default_repo_root(
    tmp_path, monkeypatch
):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)

    url = _unreachable_urls()[0]
    monkeypatch.setenv("VAR_CACHE_STORE_URL", url)

    key = _make_key("9")

    try:
        result = cache_manager.get(key)
    except Exception as exc:  # pragma: no cover - failure path
        pytest.fail(
            "get raised %s(%r) on an unreachable backing store (%s) with the "
            "default repo_root; R-CACHE-004 requires it to return Miss instead"
            % (type(exc).__name__, exc, url)
        )

    _assert_miss(result)


def test_repeated_gets_against_unreachable_store_all_miss_and_compare_equal(
    tmp_path, monkeypatch
):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)

    url = _unreachable_urls()[0]
    monkeypatch.setenv("VAR_CACHE_STORE_URL", url)

    results = []
    for suffix in ("2", "3", "2"):
        try:
            results.append(cache_manager.get(_make_key(suffix), repo_root=repo_root))
        except Exception as exc:  # pragma: no cover - failure path
            pytest.fail(
                "get raised %s(%r) on an unreachable backing store (%s); "
                "R-CACHE-004 requires it to return Miss instead"
                % (type(exc).__name__, exc, url)
            )

    for result in results:
        _assert_miss(result)

    # Any two Miss instances compare equal (interface contract).
    assert results[0] == results[1]
    assert results[1] == results[2]