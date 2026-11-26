# hotdocs-criterion: sha256:cecfa9fd342cc1a58fae6e64cca3eb3cda5a048d0402e10406fb659a000a3f58
import json
import urllib.request

import llm_endpoint


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _isolate(monkeypatch, tmp_path):
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    monkeypatch.chdir(tmp_path)


def test_parse_ollama_prefix_and_bare_tag(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)

    provider, model = llm_endpoint.parse_model("ollama:llama3.1:8b")
    assert provider == "ollama"
    assert model == "llama3.1:8b"

    provider, model = llm_endpoint.parse_model("llama3.1:8b")
    assert provider is None
    assert model == "llama3.1:8b"


def test_bare_name_uses_config_and_other_prefix_uses_its_defaults(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)

    toml_text = (
        "[llm]\n"
        + "provider = " + json.dumps("openai") + "\n"
        + "model = " + json.dumps("gpt-6-astra") + "\n"
        + "api_key_env = " + json.dumps("MY_KEY") + "\n"
        + "timeout_seconds = 400\n"
    )
    config_path = tmp_path / "hotdocs.toml"
    config_path.write_text(toml_text, encoding="utf-8")

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
    assert field(gem, "base_url") == "https://generativelanguage.googleapis.com"
    assert field(gem, "api_key_env") == "GEMINI_API_KEY"
    assert field(gem, "timeout_seconds") == llm_endpoint.DEFAULT_TIMEOUT_SECONDS


class _FakeResponse:
    def __init__(self, body):
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self, *args, **kwargs):
        return self._body


def test_provider_gets_stripped_model_but_response_keeps_identifier(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-real")

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

    def recorder(request, timeout=None, *args, **kwargs):
        recorded.append(request)
        return _FakeResponse(json.dumps(reply).encode("utf-8"))

    monkeypatch.setattr(urllib.request, "urlopen", recorder)

    resp = llm_endpoint.complete("hi", "anthropic:claude-sonnet-5-5")

    assert len(recorded) >= 1
    data = recorded[-1].data
    if isinstance(data, bytes):
        data = data.decode("utf-8")
    body = json.loads(data)
    assert body["model"] == "claude-sonnet-5-5"

    assert field(resp, "model") == "anthropic:claude-sonnet-5-5"
    assert field(resp, "model_call_error") is None


def test_injected_backend_receives_identifier_unchanged(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    log_path = tmp_path / "backend.log"

    def backend(prompt, model, **params):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(model + "\n")
        return {
            "text": "ok",
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    resp = llm_endpoint.complete("hi", "anthropic:claude-sonnet-5-5", backend=backend)

    lines = log_path.read_text(encoding="utf-8").splitlines()
    assert lines == ["anthropic:claude-sonnet-5-5"]
    assert field(resp, "model") == "anthropic:claude-sonnet-5-5"