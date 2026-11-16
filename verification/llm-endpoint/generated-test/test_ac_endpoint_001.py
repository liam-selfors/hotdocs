import subprocess
import urllib.request

import pytest

import llm_endpoint


def _install_call_guards(monkeypatch, calls):
    """Record (and refuse) any attempted network or subprocess call."""

    def fake_urlopen(*args, **kwargs):
        calls.append(("urlopen", args, kwargs))
        raise AssertionError("no HTTP call may be attempted before resolution succeeds")

    def make_fake_sub(name):
        def fake(*args, **kwargs):
            calls.append((name, args, kwargs))
            raise AssertionError("no subprocess may be started before resolution succeeds")

        return fake

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    for name in ("run", "Popen", "call", "check_call", "check_output"):
        monkeypatch.setattr(subprocess, name, make_fake_sub(name))


@pytest.fixture
def fresh_dir(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.chdir(work)
    assert not (work / "hotdocs.toml").exists()
    return work


def _error_type():
    err = getattr(llm_endpoint, "ModelResolutionError", None)
    assert err is not None, "llm_endpoint must expose ModelResolutionError"
    assert isinstance(err, type) and issubclass(err, BaseException)
    return err


def test_unmatched_bare_model_without_config_raises_usage_error(fresh_dir, monkeypatch):
    err_type = _error_type()
    calls = []
    _install_call_guards(monkeypatch, calls)

    with pytest.raises(err_type) as excinfo:
        llm_endpoint.complete("Say hello.", "gpt-5")

    # A raised resolution error, never a returned ModelResponse with model_call_error.
    assert isinstance(excinfo.value, err_type)
    # Raised before any call is attempted.
    assert calls == []


def _write_openai_compatible_without_base_url(directory):
    (directory / "hotdocs.toml").write_text(
        "[llm]\n"
        'provider = "openai-compatible"\n'
        'model = "my-local-model"\n',
        encoding="utf-8",
    )


@pytest.mark.parametrize("model", ["my-local-model", "openai-compatible:my-local-model"])
def test_openai_compatible_without_base_url_raises_usage_error(fresh_dir, monkeypatch, model):
    err_type = _error_type()
    _write_openai_compatible_without_base_url(fresh_dir)
    calls = []
    _install_call_guards(monkeypatch, calls)

    with pytest.raises(err_type):
        llm_endpoint.complete("Say hello.", model)

    assert calls == []


def test_missing_base_url_error_is_same_as_invalid_config_error(fresh_dir, monkeypatch):
    err_type = _error_type()
    calls = []
    _install_call_guards(monkeypatch, calls)

    # Invalid hotdocs.toml (not parseable TOML).
    (fresh_dir / "hotdocs.toml").write_text(
        "[llm\nprovider = = \"openai\n", encoding="utf-8"
    )
    with pytest.raises(err_type) as invalid_info:
        llm_endpoint.complete("Say hello.", "my-local-model")

    # openai-compatible with no base_url.
    _write_openai_compatible_without_base_url(fresh_dir)
    with pytest.raises(err_type) as missing_info:
        llm_endpoint.complete("Say hello.", "my-local-model")

    assert isinstance(invalid_info.value, err_type)
    assert isinstance(missing_info.value, err_type)
    assert calls == []