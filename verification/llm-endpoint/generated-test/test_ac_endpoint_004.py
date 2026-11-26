# hotdocs-criterion: sha256:7c8335081fe5a8bae6e09b846ee3546bfbdd44cbc36b759fa40f22ec5936b20c
import io
import urllib.error
import urllib.request
from pathlib import Path

import pytest

import llm_endpoint


SECRET = "sk-SECRET-123"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _fake_urlopen(request, timeout=None, *args, **kwargs):
    try:
        url = request.full_url
    except AttributeError:
        url = str(request)
    body = ('{"error": "invalid api key ' + SECRET + '"}').encode("utf-8")
    raise urllib.error.HTTPError(
        url,
        401,
        "Unauthorized: " + SECRET,
        {},
        io.BytesIO(body),
    )


def test_credential_never_appears_in_response_log_or_check_result(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    workdir = tmp_path / "work"
    workdir.mkdir()
    monkeypatch.chdir(workdir)
    for name in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY"):
        monkeypatch.setenv(name, SECRET)
    monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen)

    responses = []
    for model in ("anthropic:m", "openai:m", "gemini:m"):
        responses.append(llm_endpoint.complete("hello", model))

    results = []
    for provider in ("anthropic", "openai", "gemini"):
        results.append(llm_endpoint.check_connection(provider, "m"))

    for response in responses:
        assert field(response, "model_call_error") is not None
        for key in ("text", "model", "backend", "model_call_error"):
            assert SECRET not in repr(field(response, key))
        assert SECRET not in repr(response)

    for result in results:
        assert SECRET not in repr(field(result, "ok"))
        assert SECRET not in repr(field(result, "error"))
        assert SECRET not in repr(result)

    calls_dir = workdir / ".hotdocs" / "calls"
    files = [p for p in calls_dir.rglob("*") if p.is_file()] if calls_dir.exists() else []
    assert len(files) >= 3
    for path in files:
        content = path.read_bytes().decode("utf-8", errors="replace")
        assert SECRET not in content


def test_save_config_refuses_key_as_api_key_env(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", SECRET)
    config_path = tmp_path / "hotdocs.toml"
    with pytest.raises(ValueError) as excinfo:
        llm_endpoint.save_config(config_path, "openai", "m", api_key_env=SECRET)
    assert "never the key itself" in str(excinfo.value)
    assert not config_path.exists()