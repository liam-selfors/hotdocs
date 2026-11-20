# hotdocs-criterion: sha256:20ff1c95bfab1f2490fb155260635c416abb31a7c8ba0d1c14659310cc518f1d
import json
from pathlib import Path

import pytest
import urllib.request

import llm_endpoint


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.chdir(work)
    return work


def test_ollama_tag_colon_is_part_of_model_name(isolated):
    assert tuple(llm_endpoint.parse_model("ollama:llama3.1:8b")) == ("ollama", "llama3.1:8b")
    assert tuple(llm_endpoint.parse_model("llama3.1:8b")) == (None, "llama3.1:8b")

    resolved = llm_endpoint.resolve_provider("ollama:llama3.1:8b", None)
    assert field(resolved, "provider") == "ollama"
    assert field(resolved, "model") == "llama3.1:8b"


def test_bare_name_uses_config_and_other_prefix_uses_its_defaults(isolated):
    cfg_dir = isolated / "cfg"
    cfg_dir.mkdir()
    cfg_path = cfg_dir / "hotdocs.toml"
    cfg_path.write_text(
        "[llm]\n"
        + "provider = " + json.dumps("openai") + "\n"
        + "model = " + json.dumps("gpt-6-astra") + "\n"
        + "api_key_env = " + json.dumps("MY_KEY") + "\n"
        + "timeout_seconds = 400\n"
    )
    config = llm_endpoint.load_config(cfg_path)
    assert config is not None

    bare = llm_endpoint.resolve_provider("gpt-6-astra-mini", config)
    assert field(bare, "provider") == "openai"
    assert field(bare, "model") == "gpt-6-astra-mini"
    assert field(bare, "api_key_env") == "MY_KEY"
    assert field(bare, "timeout_seconds") == 400

    gem = llm_endpoint.resolve_provider("gemini:gemini-4-argon", config)
    assert field(gem, "provider") == "gemini"
    assert field(gem, "model") == "gemini-4-argon"
    assert field(gem, "api_key_env") == "GEMINI_API_KEY"
    assert field(gem, "base_url") == "https://generativelanguage.googleapis.com"
    assert field(gem, "timeout_seconds") == llm_endpoint.DEFAULT_TIMEOUT_SECONDS
    assert llm_endpoint.DEFAULT_TIMEOUT_SECONDS == 600


class _FakeResponse:
    def __init__(self, body):
        self._body = body
        self.status = 200

    def read(self, *args, **kwargs):
        return self._body

    def getcode(self):
        return 200

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_provider_gets_stripped_model_but_response_keeps_identifier(isolated, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-not-real")
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

    def fake_urlopen(request, *args, **kwargs):
        recorded.append(request)
        return _FakeResponse(json.dumps(reply).encode("utf-8"))

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    identifier = "anthropic:claude-sonnet-5-5"
    resp = llm_endpoint.complete("hi", identifier)

    with_body = [r for r in recorded if getattr(r, "data", None)]
    assert with_body, "no request with a body was recorded"
    data = with_body[-1].data
    if isinstance(data, (bytes, bytearray)):
        data = data.decode("utf-8")
    body = json.loads(data)
    assert body["model"] == "claude-sonnet-5-5"

    assert field(resp, "model") == identifier
    assert field(resp, "model_call_error") is None
    assert field(resp, "text") == "hello"


def test_injected_backend_receives_identifier_unchanged(isolated):
    log = isolated / "backend_calls.log"
    identifier = "anthropic:claude-sonnet-5-5"

    def backend(prompt, model, **params):
        with open(log, "a") as fh:
            fh.write(json.dumps({"prompt": prompt, "model": model}) + "\n")
        return {
            "text": "ok",
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    resp = llm_endpoint.complete("hi", identifier, backend=backend)

    lines = [json.loads(l) for l in Path(log).read_text().splitlines() if l.strip()]
    assert len(lines) == 1
    assert lines[0]["model"] == identifier
    assert lines[0]["prompt"] == "hi"
    assert field(resp, "model") == identifier