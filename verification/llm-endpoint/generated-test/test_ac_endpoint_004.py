# hotdocs-criterion: sha256:d6781545cbfe067bfcfb0e4966faac55b95907ccb982ea6964330f14590e6aa9
import io
import json
import urllib.error
import urllib.request

import pytest

import llm_endpoint


SECRET = "sk-SECRET-123"
PROVIDERS_UNDER_TEST = ["anthropic", "openai", "gemini"]


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _dump(value):
    try:
        text = json.dumps(value, default=str)
    except Exception:
        text = ""
    return text + "\n" + repr(value)


@pytest.fixture
def secret_env(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    workdir = tmp_path / "work"
    workdir.mkdir()
    monkeypatch.chdir(workdir)
    monkeypatch.setenv("ANTHROPIC_API_KEY", SECRET)
    monkeypatch.setenv("OPENAI_API_KEY", SECRET)
    monkeypatch.setenv("GEMINI_API_KEY", SECRET)

    calls = []

    def fake_urlopen(request, timeout=None, *args, **kwargs):
        url = request.full_url if hasattr(request, "full_url") else str(request)
        calls.append(url)
        body = ("{\"error\": \"invalid api key " + SECRET + "\"}").encode("utf-8")
        raise urllib.error.HTTPError(
            url,
            401,
            "Unauthorized: " + SECRET,
            {},
            io.BytesIO(body),
        )

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    return workdir, calls


def _call_log_texts(workdir):
    calls_dir = workdir / ".hotdocs" / "calls"
    texts = []
    if calls_dir.is_dir():
        for path in sorted(calls_dir.rglob("*")):
            if path.is_file():
                texts.append((path, path.read_text(encoding="utf-8", errors="replace")))
    return texts


def test_secret_never_in_responses_logs_or_check_results(secret_env):
    workdir, calls = secret_env

    responses = []
    for provider in PROVIDERS_UNDER_TEST:
        resp = llm_endpoint.complete("hello", provider + ":m")
        responses.append(resp)

    for resp in responses:
        assert SECRET not in _dump(resp)
        # The 401 should surface as a model_call_error, never text.
        err = field(resp, "model_call_error")
        assert err is not None
        assert SECRET not in _dump(err)

    results = []
    for provider in PROVIDERS_UNDER_TEST:
        result = llm_endpoint.check_connection(provider, "m")
        results.append(result)

    for result in results:
        assert SECRET not in _dump(result)
        assert field(result, "ok") is False
        error = field(result, "error")
        if error is not None:
            assert SECRET not in _dump(error)

    logs = _call_log_texts(workdir)
    assert logs, "complete() must write call log files under .hotdocs/calls/"
    for path, text in logs:
        assert SECRET not in text, "secret leaked into " + str(path)


def test_save_config_refuses_key_as_api_key_env(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", SECRET)
    workdir = tmp_path / "work"
    workdir.mkdir()
    monkeypatch.chdir(workdir)

    config_dir = tmp_path / "cfg"
    config_dir.mkdir()
    config_path = config_dir / "hotdocs.toml"

    with pytest.raises(ValueError) as excinfo:
        llm_endpoint.save_config(config_path, "openai", "m", api_key_env=SECRET)

    assert "never the key itself" in str(excinfo.value)
    assert not config_path.exists()