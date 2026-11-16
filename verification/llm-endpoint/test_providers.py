"""Hand tests for the multi-provider llm-endpoint (R-ENDPOINT-002/003/007/008/009).

HTTP providers are exercised by replacing urllib.request.urlopen (see
conftest.FakeUrlopen) -- no server is ever started.
"""

import json
import socket
import urllib.error

import pytest

import llm_endpoint
from conftest import http_error
from llm_endpoint import (
    PROVIDERS, check_connection, complete, detect_providers, load_config,
    parse_model, resolve_provider, save_config,
)

SECRET = "sk-TOTALLY-SECRET-KEY-VALUE-123"


def _write_config(directory, provider, model="m", **extra):
    save_config(directory / "hotdocs.toml", provider, model, **extra)


def _calls(cwd):
    d = cwd / ".hotdocs" / "calls"
    return [p.read_text(encoding="utf-8") for p in d.glob("*.json")] if d.exists() else []


# --------------------------------------------------------------- grammar ----

@pytest.mark.parametrize("model, expected", [
    ("claude-sonnet-5", (None, "claude-sonnet-5")),
    ("anthropic:claude-sonnet-5-5", ("anthropic", "claude-sonnet-5-5")),
    ("llama3.1:8b", (None, "llama3.1:8b")),                 # an Ollama tag, not a provider
    ("ollama:llama3.1:8b", ("ollama", "llama3.1:8b")),
    ("openai-compatible:my-model", ("openai-compatible", "my-model")),
    ("nonsense:thing", (None, "nonsense:thing")),
])
def test_parse_model(model, expected):
    assert parse_model(model) == expected


def test_provider_prefix_with_no_model_is_a_resolution_error():
    with pytest.raises(llm_endpoint.ModelResolutionError):
        parse_model("ollama:")


def test_unconfigured_bare_claude_uses_the_cli_and_other_names_fail(isolated_cwd, clean_env):
    assert resolve_provider("claude-sonnet-5")["provider"] == "claude-cli"
    with pytest.raises(llm_endpoint.ModelResolutionError):
        resolve_provider("gpt-6-astra")


def test_configured_provider_takes_bare_names_and_prefix_overrides(isolated_cwd, clean_env):
    cfg = {"provider": "openai", "model": "x", "base_url": None, "api_key_env": "MY_KEY", "timeout_seconds": 400}
    bare = resolve_provider("gpt-6-astra", cfg)
    assert bare["provider"] == "openai"
    assert bare["api_key_env"] == "MY_KEY" and bare["timeout_seconds"] == 400
    assert bare["base_url"] == "https://api.openai.com/v1"
    other = resolve_provider("gemini:gemini-4-argon", cfg)
    assert other["provider"] == "gemini"
    assert other["api_key_env"] == "GEMINI_API_KEY"          # config applies only to its own provider
    assert other["timeout_seconds"] == llm_endpoint.DEFAULT_TIMEOUT_SECONDS


def test_openai_compatible_without_base_url_is_a_resolution_error(isolated_cwd, clean_env):
    with pytest.raises(llm_endpoint.ModelResolutionError):
        resolve_provider("openai-compatible:foo")


def test_legacy_resolve_backend_name_is_unchanged():
    assert llm_endpoint.resolve_backend_name("claude-sonnet-5") == "anthropic"


# ------------------------------------------------------------ claude-cli ----

class _Done:
    returncode, stdout, stderr = 0, "ok", ""


def test_claude_cli_prefix_dispatches_and_keeps_the_callers_model_string(isolated_cwd, clean_env, monkeypatch):
    captured = {}
    monkeypatch.setattr(llm_endpoint.subprocess, "run", lambda cmd, **kw: captured.update(cmd=cmd, kw=kw) or _Done())
    response = complete("hi", "claude-cli:claude-sonnet-5")
    assert captured["cmd"][captured["cmd"].index("--model") + 1] == "claude-sonnet-5"
    assert "--tools" in captured["cmd"] and "--safe-mode" in captured["cmd"]
    assert response["model"] == "claude-cli:claude-sonnet-5"
    assert response["backend"] == "claude-cli"
    assert response["text"] == "ok"


# ------------------------------------------------------------- anthropic ----

def test_anthropic_request_shape_and_text_blocks_only(isolated_cwd, clean_env, monkeypatch, fake_urlopen):
    monkeypatch.setenv("ANTHROPIC_API_KEY", SECRET)
    fake = fake_urlopen({"content": [
        {"type": "thinking", "thinking": "hmm"},
        {"type": "text", "text": "hel"}, {"type": "text", "text": "lo"},
    ]})
    response = complete("say hi", "anthropic:claude-sonnet-5-5")
    assert fake.last.full_url == "https://api.anthropic.com/v1/messages"
    assert fake.last.get_method() == "POST"
    assert fake.header("x-api-key") == SECRET
    assert fake.header("anthropic-version") == "2023-06-01"
    assert fake.header("content-type") == "application/json"
    body = fake.body()
    assert body["model"] == "claude-sonnet-5-5"
    assert body["max_tokens"] == 32000
    assert body["messages"] == [{"role": "user", "content": "say hi"}]
    assert response["text"] == "hello"
    assert response["model"] == "anthropic:claude-sonnet-5-5"
    assert response["backend"] == "anthropic"
    assert fake.requests[0][1] == llm_endpoint.DEFAULT_TIMEOUT_SECONDS


def test_anthropic_max_tokens_and_temperature_pass_through(isolated_cwd, clean_env, monkeypatch, fake_urlopen):
    monkeypatch.setenv("ANTHROPIC_API_KEY", SECRET)
    fake = fake_urlopen({"content": [{"type": "text", "text": "x"}]})
    complete("p", "anthropic:m", max_tokens=100, temperature=0.2)
    assert fake.body()["max_tokens"] == 100 and fake.body()["temperature"] == 0.2


def test_anthropic_without_a_key_is_an_auth_error_and_makes_no_call(isolated_cwd, clean_env, fake_urlopen):
    fake = fake_urlopen()
    response = complete("p", "anthropic:m")
    assert response["model_call_error"]["category"] == "auth"
    assert "ANTHROPIC_API_KEY" in response["model_call_error"]["message"]
    assert fake.requests == []


# --------------------------------------------------------------- openai ----

def test_openai_request_shape(isolated_cwd, clean_env, monkeypatch, fake_urlopen):
    monkeypatch.setenv("OPENAI_API_KEY", SECRET)
    fake = fake_urlopen({"choices": [{"message": {"content": "hello"}}]})
    response = complete("say hi", "openai:gpt-6-astra", max_tokens=50)
    assert fake.last.full_url == "https://api.openai.com/v1/chat/completions"
    assert fake.header("authorization") == f"Bearer {SECRET}"
    body = fake.body()
    assert body["model"] == "gpt-6-astra"
    assert body["messages"] == [{"role": "user", "content": "say hi"}]
    assert body["max_completion_tokens"] == 50 and "max_tokens" not in body
    assert response["text"] == "hello" and response["backend"] == "openai"


def test_openai_null_content_is_an_error_not_a_pass(isolated_cwd, clean_env, monkeypatch, fake_urlopen):
    monkeypatch.setenv("OPENAI_API_KEY", SECRET)
    fake_urlopen({"choices": [{"message": {"content": None}}]})
    response = complete("p", "openai:m")
    assert response["text"] is None and response["model_call_error"]["category"] == "network"


# ---------------------------------------------------- openai-compatible ----

def test_openai_compatible_uses_base_url_max_tokens_and_optional_key(isolated_cwd, clean_env, monkeypatch, fake_urlopen, tmp_path):
    _write_config(isolated_cwd, "openai-compatible", "served-model", base_url="http://localhost:8000/v1/")
    fake = fake_urlopen({"choices": [{"message": {"content": "yo"}}]})
    response = complete("p", "served-model", max_tokens=7)
    assert fake.last.full_url == "http://localhost:8000/v1/chat/completions"
    assert fake.header("authorization") is None            # no key configured: none sent
    assert fake.body()["max_tokens"] == 7 and "max_completion_tokens" not in fake.body()
    assert response["text"] == "yo" and response["backend"] == "openai-compatible"

    monkeypatch.setenv("MY_LOCAL_KEY", SECRET)
    _write_config(isolated_cwd, "openai-compatible", "served-model", base_url="http://localhost:8000/v1", api_key_env="MY_LOCAL_KEY")
    fake2 = fake_urlopen({"choices": [{"message": {"content": "yo"}}]})
    complete("p", "served-model")
    assert fake2.header("authorization") == f"Bearer {SECRET}"


# --------------------------------------------------------------- gemini ----

def test_gemini_request_shape_key_in_header_never_the_url(isolated_cwd, clean_env, monkeypatch, fake_urlopen):
    monkeypatch.setenv("GEMINI_API_KEY", SECRET)
    fake = fake_urlopen({"candidates": [{"content": {"parts": [
        {"text": "thinking...", "thought": True}, {"text": "hel"}, {"text": "lo"}]}}]})
    response = complete("say hi", "gemini:models/gemini-4-argon", max_tokens=64, temperature=0.1)
    assert fake.last.full_url == "https://generativelanguage.googleapis.com/v1beta/models/gemini-4-argon:generateContent"
    assert SECRET not in fake.last.full_url
    assert fake.header("x-goog-api-key") == SECRET
    body = fake.body()
    assert body["contents"] == [{"role": "user", "parts": [{"text": "say hi"}]}]
    assert body["generationConfig"] == {"maxOutputTokens": 64, "temperature": 0.1}
    assert response["text"] == "hello" and response["backend"] == "gemini"


def test_gemini_invalid_key_reported_as_400_is_still_auth(isolated_cwd, clean_env, monkeypatch, fake_urlopen):
    monkeypatch.setenv("GEMINI_API_KEY", SECRET)
    fake_urlopen(http_error(400, '{"error":{"status":"INVALID_ARGUMENT","message":"API key not valid. Please pass a valid API key."}}'))
    assert complete("p", "gemini:m")["model_call_error"]["category"] == "auth"
    fake_urlopen(http_error(400, '{"error":{"message":"bad field"}}'))
    assert complete("p", "gemini:m")["model_call_error"]["category"] == "network"


# --------------------------------------------------------------- ollama ----

def test_ollama_request_shape_and_no_key(isolated_cwd, clean_env, fake_urlopen):
    fake = fake_urlopen({"message": {"role": "assistant", "content": "hello"}})
    response = complete("say hi", "ollama:llama3.1:8b", max_tokens=33, num_ctx=16384)
    assert fake.last.full_url == "http://localhost:11434/api/chat"
    assert fake.header("authorization") is None
    body = fake.body()
    assert body["model"] == "llama3.1:8b" and body["stream"] is False
    assert body["options"] == {"num_predict": 33, "num_ctx": 16384}
    assert response["text"] == "hello" and response["model"] == "ollama:llama3.1:8b"


# ------------------------------------------- error mapping, every provider ----

_PROVIDER_CALLS = [
    ("anthropic:m", {"ANTHROPIC_API_KEY": SECRET}),
    ("openai:m", {"OPENAI_API_KEY": SECRET}),
    ("gemini:m", {"GEMINI_API_KEY": SECRET}),
    ("ollama:m", {}),
]


@pytest.mark.parametrize("model, env", _PROVIDER_CALLS)
@pytest.mark.parametrize("outcome, category", [
    (http_error(401), "auth"), (http_error(403), "auth"),
    (http_error(429), "rate_limit"),
    (http_error(408), "timeout"), (http_error(504), "timeout"),
    (http_error(500), "network"), (http_error(529), "network"),
    (socket.timeout("t"), "timeout"), (TimeoutError("t"), "timeout"),
    (urllib.error.URLError(socket.timeout("t")), "timeout"),
    (urllib.error.URLError(ConnectionRefusedError("no")), "network"),
    (b"<html>not json</html>", "network"),
    ({"unexpected": "shape"}, "network"),
])
def test_error_mapping_never_raises_never_retries_never_leaks(
    isolated_cwd, clean_env, monkeypatch, fake_urlopen, model, env, outcome, category
):
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    # A vendor that echoes the credential in its error body must not leak it.
    if isinstance(outcome, urllib.error.HTTPError):
        outcome = http_error(outcome.code, f"bad key {SECRET}")
    fake = fake_urlopen(outcome, outcome)
    response = complete("p", model)
    assert response["text"] is None
    assert response["model_call_error"]["category"] == category
    assert len(fake.requests) == 1                       # no retry
    assert SECRET not in json.dumps(response)
    assert all(SECRET not in text for text in _calls(isolated_cwd))


# ------------------------------------------------------------------ config ----

@pytest.mark.parametrize("provider, extra", [
    ("claude-cli", {}),
    ("anthropic", {"api_key_env": "ANTHROPIC_API_KEY"}),
    ("openai", {"api_key_env": "OPENAI_API_KEY", "timeout_seconds": 900}),
    ("openai-compatible", {"base_url": "http://localhost:8000/v1"}),
    ("gemini", {"api_key_env": "GEMINI_API_KEY"}),
    ("ollama", {"base_url": "http://localhost:11434"}),
])
def test_save_then_load_round_trips(tmp_path, clean_env, provider, extra):
    path = tmp_path / "nested" / "dir" / "hotdocs.toml"
    save_config(path, provider, "some-model", **extra)
    cfg = load_config(path)
    assert cfg["provider"] == provider and cfg["model"] == "some-model"
    for key, value in extra.items():
        assert cfg[key] == value


def test_save_replaces_only_the_llm_table_and_keeps_the_rest(tmp_path, clean_env):
    path = tmp_path / "hotdocs.toml"
    path.write_text('title = "x"\n\n[other]\na = 1\n\n[llm]\nprovider = "ollama"\nmodel = "old"\n\n[tail]\nb = 2\n', encoding="utf-8")
    save_config(path, "gemini", "gemini-4-argon", api_key_env="GEMINI_API_KEY")
    text = path.read_text(encoding="utf-8")
    assert 'title = "x"' in text and "[other]" in text and "[tail]" in text and "old" not in text
    assert load_config(path)["provider"] == "gemini"
    assert text.count("[llm]") == 1


def test_save_refuses_bad_input_and_writes_nothing(tmp_path, clean_env, monkeypatch):
    path = tmp_path / "hotdocs.toml"
    monkeypatch.setenv("REAL_KEY_VAR", SECRET)
    bad = [
        dict(provider="skynet", model="m"),
        dict(provider="openai", model=""),
        dict(provider="openai-compatible", model="m"),                       # base_url required
        dict(provider="claude-cli", model="m", base_url="http://x"),
        dict(provider="openai", model="m", base_url="ftp://x"),
        dict(provider="openai", model="m", api_key_env=SECRET),              # a key, not a name
        dict(provider="openai", model="m", api_key_env="has space"),
        dict(provider="openai", model="m", timeout_seconds=120),             # below the 300 s floor
    ]
    for kwargs in bad:
        with pytest.raises(ValueError):
            save_config(path, **kwargs)
    assert not path.exists()


def test_a_pasted_key_that_looks_like_a_variable_name_is_still_refused(tmp_path, clean_env, monkeypatch):
    # Matches the variable-name pattern, but equals the VALUE of an env var.
    monkeypatch.setenv("REAL_KEY_VAR", "PASTEDKEYVALUE123")
    with pytest.raises(ValueError, match="never the key itself"):
        save_config(tmp_path / "hotdocs.toml", "openai", "m", api_key_env="PASTEDKEYVALUE123")
    assert not (tmp_path / "hotdocs.toml").exists()
    save_config(tmp_path / "hotdocs.toml", "openai", "m", api_key_env="REAL_KEY_VAR")   # the NAME is fine


def test_a_saved_config_never_contains_a_secret(tmp_path, clean_env, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", SECRET)
    path = tmp_path / "hotdocs.toml"
    save_config(path, "openai", "gpt-6-astra", api_key_env="OPENAI_API_KEY")
    assert SECRET not in path.read_text(encoding="utf-8")
    assert "OPENAI_API_KEY" in path.read_text(encoding="utf-8")


def test_load_config_rejects_secrets_unknown_keys_and_bad_files(tmp_path, clean_env):
    def write(text):
        p = tmp_path / "c.toml"
        p.write_text(text, encoding="utf-8")
        return p

    with pytest.raises(ValueError, match="secret"):
        load_config(write('[llm]\nprovider="openai"\nmodel="m"\napi_key="sk-123"\n'))
    with pytest.raises(ValueError, match="unknown"):
        load_config(write('[llm]\nprovider="openai"\nmodel="m"\nflavour="x"\n'))
    with pytest.raises(ValueError, match="provider"):
        load_config(write('[llm]\nprovider="nope"\nmodel="m"\n'))
    with pytest.raises(ValueError):  # R-ENDPOINT-007: names the problem; no wording is specified
        load_config(write("[llm\n"))
    assert load_config(write("[other]\nx = 1\n")) is None          # no [llm] table
    assert load_config(tmp_path / "missing.toml") is None
    assert load_config(write('[llm]\nprovider="openai"\nmodel="m"\nbase_url=""\napi_key_env=""\n'))["base_url"] is None


def test_config_discovery_order_and_failures(tmp_path, isolated_cwd, clean_env, monkeypatch):
    assert load_config() is None
    _write_config(isolated_cwd, "ollama", "from-cwd")
    assert load_config()["model"] == "from-cwd"
    elsewhere = tmp_path / "elsewhere.toml"
    save_config(elsewhere, "openai", "from-env", api_key_env="OPENAI_API_KEY")
    monkeypatch.setenv("VAR_HOTDOCS_CONFIG", str(elsewhere))
    assert load_config()["model"] == "from-env"                     # env var wins over ./hotdocs.toml
    monkeypatch.setenv("VAR_HOTDOCS_CONFIG", str(tmp_path / "gone.toml"))
    with pytest.raises(ValueError):
        load_config()
    with pytest.raises(llm_endpoint.ModelResolutionError):          # complete() reports it as a config mistake
        complete("p", "anything")


# ------------------------------------------------------ setup helpers ----

def test_detect_providers_reports_each_provider_from_the_given_env(clean_env, fake_urlopen):
    fake_urlopen(OSError("refused"))
    found = {e["provider"]: e for e in detect_providers(
        env={"PATH": "/nonexistent", "OPENAI_API_KEY": SECRET, "GEMINI_API_KEY": "  "}, probe_ollama=True)}
    assert list(found) == list(PROVIDERS)
    assert found["claude-cli"]["available"] is False
    assert found["openai"]["available"] is True and found["openai"]["api_key_env"] == "OPENAI_API_KEY"
    assert found["gemini"]["available"] is False                    # blank key does not count
    assert found["anthropic"]["available"] is False
    assert found["ollama"]["available"] is False
    assert found["openai-compatible"]["available"] is False
    for entry in found.values():
        assert set(entry) == {"provider", "available", "reason", "suggested_model", "api_key_env"}
    assert SECRET not in json.dumps(list(found.values()))


def test_detect_providers_finds_claude_on_path_and_a_live_ollama(tmp_path, clean_env, fake_urlopen):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    exe = bin_dir / "claude"
    exe.write_text("#!/bin/sh\n")
    exe.chmod(0o755)
    fake = fake_urlopen({"models": []})
    found = {e["provider"]: e for e in detect_providers(env={"PATH": str(bin_dir)})}
    assert found["claude-cli"]["available"] is True
    assert found["ollama"]["available"] is True
    assert fake.last.full_url == "http://localhost:11434/api/tags" and fake.requests[0][1] == 1
    skipped = {e["provider"]: e for e in detect_providers(env={"PATH": ""}, probe_ollama=False)}
    assert skipped["ollama"]["available"] is False and len(fake.requests) == 1


def test_check_connection_ok_and_error(isolated_cwd, clean_env, monkeypatch, fake_urlopen):
    monkeypatch.setenv("OPENAI_API_KEY", SECRET)
    fake = fake_urlopen({"choices": [{"message": {"content": "ok"}}]})
    assert check_connection("openai", "gpt-6-astra") == {"ok": True, "error": None}
    assert fake.requests[0][1] == 30 and fake.body()["max_completion_tokens"] == 1024
    fake_urlopen(http_error(401, f"nope {SECRET}"))
    result = check_connection("openai", "gpt-6-astra")
    assert result["ok"] is False and result["error"]["category"] == "auth"
    assert SECRET not in json.dumps(result)
    assert not (isolated_cwd / ".hotdocs").exists()                  # a probe is not logged as a pipeline call


def test_check_connection_other_providers_and_arguments(isolated_cwd, clean_env, monkeypatch, fake_urlopen):
    fake = fake_urlopen({"message": {"content": "ok"}})
    assert check_connection("ollama", "llama3.2", base_url="http://gpu-box:11434", timeout_seconds=5)["ok"] is True
    assert fake.last.full_url == "http://gpu-box:11434/api/chat" and fake.requests[0][1] == 5
    monkeypatch.setenv("CUSTOM_KEY", SECRET)
    fake2 = fake_urlopen({"choices": [{"message": {"content": "ok"}}]})
    check_connection("openai-compatible", "m", base_url="http://h/v1", api_key_env="CUSTOM_KEY")
    assert fake2.header("authorization") == f"Bearer {SECRET}"
    monkeypatch.setattr(llm_endpoint.subprocess, "run", lambda cmd, **kw: _Done())
    assert check_connection("claude-cli", "claude-sonnet-5")["ok"] is True
    with pytest.raises(ValueError):
        check_connection("skynet", "m")
    with pytest.raises(ValueError):
        check_connection("openai-compatible", "m")


def test_providers_table_shape_and_documented_defaults():
    for meta in PROVIDERS.values():
        assert set(meta) == {"default_base_url", "default_api_key_env", "needs_base_url", "suggested_model"}
    assert PROVIDERS["anthropic"]["default_base_url"] == "https://api.anthropic.com"
    assert PROVIDERS["openai"]["default_base_url"] == "https://api.openai.com/v1"
    assert PROVIDERS["gemini"]["default_base_url"] == "https://generativelanguage.googleapis.com"
    assert PROVIDERS["ollama"]["default_base_url"] == "http://localhost:11434"
    assert PROVIDERS["openai-compatible"]["needs_base_url"] is True
    assert [p for p, m in PROVIDERS.items() if m["needs_base_url"]] == ["openai-compatible"]
