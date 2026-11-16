import json
import urllib.request

import pytest

import llm_endpoint


def _field(value, name):
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.chdir(work)
    return work


def test_ollama_prefix_vs_bare_tag_with_colon(isolated):
    prefixed = llm_endpoint.parse_model("ollama:llama3.1:8b")
    assert tuple(prefixed) == ("ollama", "llama3.1:8b")

    bare = llm_endpoint.parse_model("llama3.1:8b")
    assert tuple(bare) == (None, "llama3.1:8b")

    resolved = llm_endpoint.resolve_provider("ollama:llama3.1:8b", None)
    assert _field(resolved, "provider") == "ollama"
    assert _field(resolved, "model") == "llama3.1:8b"


def test_bare_name_uses_config_and_other_prefix_uses_its_defaults(isolated):
    config_path = isolated / "hotdocs.toml"
    config_path.write_text(
        "[llm]\n"
        'provider = "openai"\n'
        'model = "gpt-6-astra"\n'
        'api_key_env = "MY_KEY"\n'
        "timeout_seconds = 400\n",
        encoding="utf-8",
    )

    config = llm_endpoint.load_config(config_path)
    assert config is not None
    assert _field(config, "provider") == "openai"
    assert _field(config, "api_key_env") == "MY_KEY"
    assert _field(config, "timeout_seconds") == 400

    bare = llm_endpoint.resolve_provider("gpt-other-model", config)
    assert _field(bare, "provider") == "openai"
    assert _field(bare, "model") == "gpt-other-model"
    assert _field(bare, "api_key_env") == "MY_KEY"
    assert _field(bare, "timeout_seconds") == 400
    assert _field(bare, "base_url") == "https://api.openai.com/v1"

    gem = llm_endpoint.resolve_provider("gemini:gemini-4-argon", config)
    assert _field(gem, "provider") == "gemini"
    assert _field(gem, "model") == "gemini-4-argon"
    assert _field(gem, "base_url") == "https://generativelanguage.googleapis.com"
    assert _field(gem, "api_key_env") == "GEMINI_API_KEY"
    assert _field(gem, "timeout_seconds") == llm_endpoint.DEFAULT_TIMEOUT_SECONDS
    assert llm_endpoint.DEFAULT_TIMEOUT_SECONDS == 600


class _FakeReply:
    def __init__(self, payload):
        self._body = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self, *args, **kwargs):
        return self._body


def test_provider_receives_stripped_model_but_response_keeps_identifier(
    isolated, monkeypatch
):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-not-a-real-key")
    recorded = []

    def recorder(request, data=None, timeout=None, *args, **kwargs):
        body = getattr(request, "data", None)
        if body is None:
            body = data
        recorded.append(body)
        return _FakeReply(
            {
                "id": "msg_test",
                "type": "message",
                "role": "assistant",
                "model": "claude-sonnet-5-5",
                "content": [{"type": "text", "text": "hello"}],
                "stop_reason": "end_turn",
                "usage": {"input_tokens": 1, "output_tokens": 1},
            }
        )

    monkeypatch.setattr(urllib.request, "urlopen", recorder)

    response = llm_endpoint.complete("hi", "anthropic:claude-sonnet-5-5")

    assert len(recorded) >= 1
    body = recorded[-1]
    assert body is not None
    if isinstance(body, (bytes, bytearray)):
        body = body.decode("utf-8")
    payload = json.loads(body)
    assert payload.get("model") == "claude-sonnet-5-5"

    assert _field(response, "model") == "anthropic:claude-sonnet-5-5"


def test_injected_backend_receives_identifier_unchanged(isolated):
    seen = []

    def backend(prompt, model, **params):
        seen.append(model)
        return {
            "text": "ok",
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    response = llm_endpoint.complete(
        "hi", "anthropic:claude-sonnet-5-5", backend=backend
    )

    assert seen == ["anthropic:claude-sonnet-5-5"]
    assert _field(response, "model") == "anthropic:claude-sonnet-5-5"