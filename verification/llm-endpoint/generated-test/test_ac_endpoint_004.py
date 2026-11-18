# hotdocs-criterion: sha256:8ce9b39c3e966ea61044c092e9cccb94bc665bcf93c921809a0772b865d5e2ea
import email.message
import io
import json
import urllib.error
import urllib.request

import pytest

import llm_endpoint


SECRET = "sk-SECRET-123"
PROVIDERS = ["anthropic", "openai", "gemini"]
KEY_VARS = ["ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY"]


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _dump(value):
    """Render a returned value (dict or object) as thoroughly as possible."""
    parts = [repr(value), str(value)]
    if isinstance(value, dict):
        try:
            parts.append(json.dumps(value, default=str))
        except Exception:
            pass
    else:
        try:
            parts.append(repr(vars(value)))
        except TypeError:
            pass
    return "\n".join(parts)


def _request_url(request):
    if isinstance(request, str):
        return request
    url = getattr(request, "full_url", None)
    if url is None:
        url = getattr(request, "get_full_url", lambda: "")()
    return url or ""


@pytest.fixture
def isolated_env(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    workdir = tmp_path / "work"
    workdir.mkdir()
    monkeypatch.chdir(workdir)
    return workdir


def test_credential_never_appears_in_responses_logs_or_check_results(
    isolated_env, monkeypatch
):
    workdir = isolated_env
    for var in KEY_VARS:
        monkeypatch.setenv(var, SECRET)

    calls = []

    def fake_urlopen(request, *args, **kwargs):
        calls.append(request)
        body = json.dumps(
            {"error": {"message": "Invalid API key: " + SECRET, "key": SECRET}}
        ).encode("utf-8")
        hdrs = email.message.Message()
        raise urllib.error.HTTPError(
            _request_url(request), 401, "Unauthorized " + SECRET, hdrs, io.BytesIO(body)
        )

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    responses = []
    for provider in PROVIDERS:
        resp = llm_endpoint.complete("hello", provider + ":m")
        responses.append((provider, resp))

    # The HTTP path was actually exercised (so the 401 echo had a chance to leak).
    assert len(calls) >= len(PROVIDERS)

    for provider, resp in responses:
        rendered = _dump(resp)
        assert SECRET not in rendered, (provider, rendered)
        for name in ("text", "model", "backend", "model_call_error"):
            assert SECRET not in repr(field(resp, name)), (provider, name)
        assert field(resp, "model_call_error") is not None, provider
        assert field(resp, "text") is None, provider

    check_results = []
    for provider in PROVIDERS:
        result = llm_endpoint.check_connection(provider, "m")
        check_results.append((provider, result))

    for provider, result in check_results:
        rendered = _dump(result)
        assert SECRET not in rendered, (provider, rendered)
        assert SECRET not in repr(field(result, "ok")), provider
        assert SECRET not in repr(field(result, "error")), provider

    calls_dir = workdir / ".hotdocs" / "calls"
    assert calls_dir.is_dir()
    files = [p for p in calls_dir.rglob("*") if p.is_file()]
    assert len(files) >= len(PROVIDERS)
    for path in files:
        data = path.read_bytes()
        assert SECRET.encode("utf-8") not in data, path


def test_save_config_refuses_key_as_api_key_env(isolated_env, tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", SECRET)
    target_dir = tmp_path / "cfgdir"
    target_dir.mkdir()
    config_path = target_dir / "hotdocs.toml"

    with pytest.raises(ValueError) as excinfo:
        llm_endpoint.save_config(config_path, "openai", "m", api_key_env=SECRET)

    assert "never the key itself" in str(excinfo.value)
    assert not config_path.exists()