# hotdocs-criterion: sha256:96aa30a52cca25661550cb914534d6870aa7a493d3c8c30033e8e852eee89e3e
import io
import json
import urllib.error
import urllib.request

import pytest

import llm_endpoint


SECRET = "sk-SECRET-123"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _all_text(value):
    parts = [repr(value)]
    try:
        parts.append(json.dumps(value, default=str))
    except Exception:
        pass
    return "\n".join(parts)


def _make_fake_urlopen(log):
    def fake_urlopen(request, timeout=None, *args, **kwargs):
        log.append(request)
        body = ('{"error": {"message": "invalid api key ' + SECRET + '"}}').encode("utf-8")
        raise urllib.error.HTTPError(
            "https://example.invalid/endpoint",
            401,
            "Unauthorized",
            {},
            io.BytesIO(body),
        )

    return fake_urlopen


def test_credential_never_appears_in_responses_call_log_or_check_results(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    workdir = tmp_path / "work"
    workdir.mkdir()
    monkeypatch.chdir(workdir)

    for name in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY"):
        monkeypatch.setenv(name, SECRET)

    calls = []
    monkeypatch.setattr(urllib.request, "urlopen", _make_fake_urlopen(calls))

    providers = ["anthropic", "openai", "gemini"]

    responses = []
    for provider in providers:
        response = llm_endpoint.complete("hello", provider + ":m")
        responses.append(response)

    check_results = []
    for provider in providers:
        result = llm_endpoint.check_connection(provider, "m")
        check_results.append(result)

    # The fake was actually reached, so the 401 body echoing the key was available.
    assert len(calls) >= 1

    for response in responses:
        text = _all_text(response)
        assert SECRET not in text
        error = field(response, "model_call_error")
        if error is not None:
            assert SECRET not in _all_text(error)
            assert SECRET not in str(field(error, "message"))

    for result in check_results:
        assert SECRET not in _all_text(result)
        error = field(result, "error")
        if error is not None:
            assert SECRET not in _all_text(error)
            assert SECRET not in str(field(error, "message"))

    calls_dir = workdir / ".hotdocs" / "calls"
    assert calls_dir.is_dir()
    files = [p for p in calls_dir.rglob("*") if p.is_file()]
    assert len(files) >= len(providers)
    for path in files:
        content = path.read_bytes()
        assert SECRET.encode("utf-8") not in content

    # Nothing anywhere under .hotdocs holds the key either.
    for path in (workdir / ".hotdocs").rglob("*"):
        if path.is_file():
            assert SECRET.encode("utf-8") not in path.read_bytes()


def test_save_config_refuses_key_as_api_key_env(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", SECRET)
    target_dir = tmp_path / "cfg"
    target_dir.mkdir()
    config_path = target_dir / "hotdocs.toml"

    with pytest.raises(ValueError) as excinfo:
        llm_endpoint.save_config(config_path, "openai", "m", api_key_env=SECRET)

    assert "never the key itself" in str(excinfo.value)
    assert not config_path.exists()