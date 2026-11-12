import io
import json
import os
import urllib.error
import urllib.request
from email.message import Message
from pathlib import Path

import pytest

import llm_endpoint


SECRET = "sk-SECRET-123"
PROVIDERS_UNDER_TEST = ["anthropic", "openai", "gemini"]
KEY_VARS = ["ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY"]


def _field(value, name):
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def _snapshot(value):
    """Render every documented field plus the whole value as text."""
    parts = [repr(value)]
    for name in ("text", "model", "backend", "model_call_error", "ok", "error"):
        field = _field(value, name)
        parts.append(repr(field))
        if field is not None:
            for sub in ("category", "message"):
                parts.append(repr(_field(field, sub)))
    try:
        parts.append(json.dumps(value, default=str))
    except Exception:
        pass
    return "\n".join(parts)


@pytest.fixture
def leaky_env(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    workdir = tmp_path / "work"
    workdir.mkdir()
    monkeypatch.chdir(workdir)
    for var in KEY_VARS:
        monkeypatch.setenv(var, SECRET)

    calls = []

    def fake_urlopen(request, *args, **kwargs):
        calls.append(request)
        body = ("{\"error\": \"invalid api key: " + SECRET + "\"}").encode("utf-8")
        hdrs = Message()
        raise urllib.error.HTTPError(
            "https://example.invalid/endpoint",
            401,
            "Unauthorized",
            hdrs,
            io.BytesIO(body),
        )

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    return workdir, calls


def test_secret_never_leaks_from_complete_call_log_or_check_connection(leaky_env):
    workdir, calls = leaky_env

    responses = []
    for provider in PROVIDERS_UNDER_TEST:
        response = llm_endpoint.complete("Say hello.", provider + ":m")
        responses.append((provider, response))

    connection_results = []
    for provider in PROVIDERS_UNDER_TEST:
        result = llm_endpoint.check_connection(provider, "m")
        connection_results.append((provider, result))

    # The faked 401 path was actually exercised.
    assert len(calls) >= len(PROVIDERS_UNDER_TEST), (
        "expected urllib.request.urlopen to be reached for each provider"
    )

    for provider, response in responses:
        assert response is not None
        assert _field(response, "text") is None, provider
        error = _field(response, "model_call_error")
        assert error is not None, provider
        assert _field(error, "category") == "auth", provider
        assert SECRET not in _snapshot(response), (
            "secret leaked into ModelResponse for " + provider
        )

    for provider, result in connection_results:
        assert result is not None
        assert not _field(result, "ok"), provider
        assert SECRET not in _snapshot(result), (
            "secret leaked into check_connection result for " + provider
        )

    calls_dir = workdir / ".hotdocs" / "calls"
    assert calls_dir.is_dir(), "expected .hotdocs/calls/ to be written"
    log_files = [p for p in calls_dir.rglob("*") if p.is_file()]
    assert len(log_files) >= len(PROVIDERS_UNDER_TEST)
    for path in log_files:
        content = path.read_bytes()
        assert SECRET.encode("utf-8") not in content, (
            "secret leaked into call log file " + str(path)
        )


def test_save_config_refuses_key_value_as_api_key_env(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", SECRET)
    target_dir = tmp_path / "cfgdir"
    config_path = target_dir / "hotdocs.toml"

    with pytest.raises(ValueError) as excinfo:
        llm_endpoint.save_config(config_path, "openai", "m", api_key_env=SECRET)

    message = str(excinfo.value)
    assert "never the key itself" in message
    assert SECRET not in message
    assert not config_path.exists()
    assert not os.path.exists(str(Path(target_dir) / "hotdocs.toml"))