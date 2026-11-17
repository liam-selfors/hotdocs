import json
import os
import urllib.request

import pytest

import llm_endpoint


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


@pytest.fixture
def clean_env(tmp_path, monkeypatch):
    workdir = tmp_path / "work"
    workdir.mkdir()
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    monkeypatch.chdir(workdir)
    return workdir


# --- Given 1: prefix counts only when it names a provider -----------------

def test_ollama_prefix_and_bare_ollama_tag(clean_env):
    provider, model = llm_endpoint.parse_model("ollama:llama3.1:8b")
    assert provider == "ollama"
    assert model == "llama3.1:8b"

    provider, model = llm_endpoint.parse_model("llama3.1:8b")
    assert provider is None
    assert model == "llama3.1:8b"


# --- Given 2: bare name uses the configured provider; another prefix uses
#     that provider's defaults ---------------------------------------------

def _write_config(directory):
    path = directory / "hotdocs.toml"
    path.write_text(
        "[llm]\n"
        'provider = "openai"\n'
        'model = "gpt-6-astra"\n'
        'api_key_env = "MY_KEY"\n'
        "timeout_seconds = 400\n",
        encoding="utf-8",
    )
    return path


def test_bare_name_uses_config_and_gemini_prefix_uses_defaults(clean_env):
    path = _write_config(clean_env)
    config = llm_endpoint.load_config(path)
    assert config is not None

    bare = llm_endpoint.resolve_provider("gpt-6-nova", config)
    assert field(bare, "provider") == "openai"
    assert field(bare, "model") == "gpt-6-nova"
    assert field(bare, "api_key_env") == "MY_KEY"
    assert field(bare, "timeout_seconds") == 400

    gem = llm_endpoint.resolve_provider("gemini:gemini-4-argon", config)
    assert field(gem, "provider") == "gemini"
    assert field(gem, "model") == "gemini-4-argon"
    assert field(gem, "base_url") == "https://generativelanguage.googleapis.com"
    assert field(gem, "api_key_env") == "GEMINI_API_KEY"
    assert field(gem, "timeout_seconds") == llm_endpoint.DEFAULT_TIMEOUT_SECONDS
    assert field(gem, "timeout_seconds") == 600


# --- Given 3: provider receives only the part after the prefix, but
#     ModelResponse.model is the identifier as passed ---------------------

class _FakeReply:
    def __init__(self, body):
        self._body = body
        self.status = 200
        self.code = 200
        self.headers = {"Content-Type": "application/json"}

    def read(self, *args, **kwargs):
        return self._body

    def getcode(self):
        return 200

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _request_body(request, args, kwargs):
    data = getattr(request, "data", None)
    if data is None and len(args) > 1:
        data = args[1]
    if data is None:
        data = kwargs.get("data")
    if isinstance(data, (bytes, bytearray)):
        data = data.decode("utf-8")
    return json.loads(data) if data else None


def test_complete_strips_prefix_for_provider_but_returns_identifier(
    clean_env, monkeypatch
):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-not-real")
    recorded = []

    reply_body = json.dumps(
        {
            "id": "msg_test",
            "type": "message",
            "role": "assistant",
            "model": "claude-sonnet-5-5",
            "content": [{"type": "text", "text": "hello"}],
            "stop_reason": "end_turn",
            "stop_sequence": None,
            "usage": {"input_tokens": 1, "output_tokens": 1},
        }
    ).encode("utf-8")

    def recorder(request, *args, **kwargs):
        recorded.append(_request_body(request, args, kwargs))
        return _FakeReply(reply_body)

    monkeypatch.setattr(urllib.request, "urlopen", recorder)

    response = llm_endpoint.complete("hi", "anthropic:claude-sonnet-5-5")

    assert recorded, "urllib.request.urlopen was never called"
    bodies = [b for b in recorded if isinstance(b, dict)]
    assert bodies, "no JSON request body was recorded"
    assert bodies[-1]["model"] == "claude-sonnet-5-5"

    assert field(response, "model") == "anthropic:claude-sonnet-5-5"
    assert field(response, "text") == "hello"
    assert field(response, "model_call_error") is None


def test_injected_backend_receives_identifier_unchanged(clean_env, tmp_path):
    log_path = tmp_path / "backend_calls.jsonl"

    def backend(prompt, model, **params):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"prompt": prompt, "model": model}) + "\n")
        return {
            "text": "ok",
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    response = llm_endpoint.complete(
        "hi", "anthropic:claude-sonnet-5-5", backend=backend
    )

    lines = [
        json.loads(line)
        for line in log_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(lines) == 1
    assert lines[0]["model"] == "anthropic:claude-sonnet-5-5"
    assert field(response, "model") == "anthropic:claude-sonnet-5-5"