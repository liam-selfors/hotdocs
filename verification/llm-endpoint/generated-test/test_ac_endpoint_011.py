# hotdocs-criterion: sha256:ef0e4965f8888292ea2f827e942c222c5beab6745f6f6168e45a3ad2e5c19192
import json

import pytest
import urllib.request

import llm_endpoint


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


@pytest.fixture
def clean_env(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.chdir(work)
    return work


def test_ollama_prefix_versus_bare_tag(clean_env):
    provider, model = llm_endpoint.parse_model("ollama:llama3.1:8b")
    assert provider == "ollama"
    assert model == "llama3.1:8b"

    provider, model = llm_endpoint.parse_model("llama3.1:8b")
    assert provider is None
    assert model == "llama3.1:8b"

    resolved = llm_endpoint.resolve_provider("ollama:llama3.1:8b", None)
    assert field(resolved, "provider") == "ollama"
    assert field(resolved, "model") == "llama3.1:8b"


def test_bare_name_uses_config_and_other_prefix_uses_defaults(clean_env):
    config_path = clean_env / "hotdocs.toml"
    config_path.write_text(
        "[llm]\n"
        "provider = " + json.dumps("openai") + "\n"
        "model = " + json.dumps("gpt-6-astra") + "\n"
        "api_key_env = " + json.dumps("MY_KEY") + "\n"
        "timeout_seconds = 400\n"
    )
    config = llm_endpoint.load_config(config_path)
    assert config is not None

    bare = llm_endpoint.resolve_provider("gpt-6-astra", config)
    assert field(bare, "provider") == "openai"
    assert field(bare, "model") == "gpt-6-astra"
    assert field(bare, "api_key_env") == "MY_KEY"
    assert field(bare, "timeout_seconds") == 400

    gem = llm_endpoint.resolve_provider("gemini:gemini-4-argon", config)
    assert field(gem, "provider") == "gemini"
    assert field(gem, "model") == "gemini-4-argon"
    assert field(gem, "api_key_env") == "GEMINI_API_KEY"
    assert field(gem, "base_url") == "https://generativelanguage.googleapis.com"
    assert field(gem, "timeout_seconds") == llm_endpoint.DEFAULT_TIMEOUT_SECONDS
    assert field(gem, "timeout_seconds") == 600


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return self._payload


def test_provider_gets_stripped_model_but_response_keeps_identifier(clean_env, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-not-a-real-key")
    recorded = []
    reply = {
        "id": "msg_test",
        "type": "message",
        "role": "assistant",
        "model": "claude-sonnet-5-5",
        "content": [{"type": "text", "text": "hello"}],
        "stop_reason": "end_turn",
        "stop_sequence": None,
        "usage": {"input_tokens": 1, "output_tokens": 1},
    }

    def recorder(request, *args, **kwargs):
        recorded.append(request)
        return _FakeResponse(json.dumps(reply).encode("utf-8"))

    monkeypatch.setattr(urllib.request, "urlopen", recorder)

    response = llm_endpoint.complete("hi", "anthropic:claude-sonnet-5-5")

    assert len(recorded) >= 1
    request = recorded[-1]
    data = request.data if hasattr(request, "data") else None
    assert data is not None
    if isinstance(data, bytes):
        data = data.decode("utf-8")
    body = json.loads(data)
    assert body["model"] == "claude-sonnet-5-5"

    assert field(response, "model") == "anthropic:claude-sonnet-5-5"
    assert field(response, "backend") == "anthropic"
    assert field(response, "model_call_error") is None


def test_injected_backend_receives_identifier_unchanged(clean_env):
    seen = []

    def backend(prompt, model, **params):
        seen.append(model)
        return {
            "text": "ok",
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    response = llm_endpoint.complete("hi", "anthropic:claude-sonnet-5-5", backend=backend)
    assert seen == ["anthropic:claude-sonnet-5-5"]
    assert field(response, "model") == "anthropic:claude-sonnet-5-5"