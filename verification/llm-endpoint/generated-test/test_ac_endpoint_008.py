# hotdocs-criterion: sha256:60f4c0372daff3d979d4a83242160a076ff43323a859d88e2f20516b214b97a9
import json
import urllib.request

import pytest

import llm_endpoint


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


class _Reply:
    def __init__(self, payload):
        self._data = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self, *args, **kwargs):
        return self._data


def _install_recorder(monkeypatch, payload):
    recorded = []

    def fake_urlopen(request, *args, **kwargs):
        recorded.append(request)
        return _Reply(payload)

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    return recorded


def _headers(request):
    out = {}
    for name, value in request.header_items():
        out[name.lower()] = value
    return out


def _url(request):
    return request.full_url if hasattr(request, "full_url") else request.get_full_url()


def _body(request):
    data = request.data
    if isinstance(data, (bytes, bytearray)):
        data = data.decode("utf-8")
    return json.loads(data)


ANTHROPIC_KEY = "sk-ant-test-key-123"
OPENAI_KEY = "sk-openai-test-key-456"
GEMINI_KEY = "gemini-test-key-789"


@pytest.fixture
def clean_env(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ANTHROPIC_API_KEY", ANTHROPIC_KEY)
    monkeypatch.setenv("OPENAI_API_KEY", OPENAI_KEY)
    monkeypatch.setenv("GEMINI_API_KEY", GEMINI_KEY)
    return tmp_path


def test_anthropic_wire_format(clean_env, monkeypatch):
    payload = {
        "id": "msg_1",
        "type": "message",
        "role": "assistant",
        "model": "m",
        "content": [
            {"type": "thinking", "thinking": "let me think", "signature": "sig"},
            {"type": "text", "text": "Hel"},
            {"type": "text", "text": "lo"},
        ],
        "stop_reason": "end_turn",
    }
    recorded = _install_recorder(monkeypatch, payload)

    result = llm_endpoint.complete("say hi", "anthropic:m", max_tokens=50)

    assert len(recorded) == 1
    req = recorded[0]
    assert req.get_method() == "POST"
    assert _url(req) == "https://api.anthropic.com/v1/messages"
    headers = _headers(req)
    assert headers.get("x-api-key") == ANTHROPIC_KEY
    assert headers.get("anthropic-version") == "2023-06-01"
    assert headers.get("user-agent")
    assert "authorization" not in headers
    body = _body(req)
    assert body["model"] == "m"
    assert body["max_tokens"] == 50
    assert "say hi" in json.dumps(body)

    assert field(result, "model_call_error") is None
    assert field(result, "text") == "Hello"
    assert field(result, "backend") == "anthropic"
    assert field(result, "model") == "anthropic:m"


def test_openai_wire_format(clean_env, monkeypatch):
    payload = {
        "id": "chatcmpl-1",
        "object": "chat.completion",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": "hi there"},
                "finish_reason": "stop",
            }
        ],
    }
    recorded = _install_recorder(monkeypatch, payload)

    result = llm_endpoint.complete("say hi", "openai:m", max_tokens=50)

    assert len(recorded) == 1
    req = recorded[0]
    assert req.get_method() == "POST"
    assert _url(req) == "https://api.openai.com/v1/chat/completions"
    headers = _headers(req)
    assert headers.get("authorization") == "Bearer " + OPENAI_KEY
    assert headers.get("user-agent")
    body = _body(req)
    assert body["model"] == "m"
    assert body["max_completion_tokens"] == 50
    assert "say hi" in json.dumps(body)

    assert field(result, "model_call_error") is None
    assert field(result, "text") == "hi there"
    assert field(result, "backend") == "openai"


def test_gemini_wire_format(clean_env, monkeypatch):
    payload = {
        "candidates": [
            {
                "content": {
                    "role": "model",
                    "parts": [
                        {"text": "internal musing", "thought": True},
                        {"text": "hello from gemini"},
                    ],
                },
                "finishReason": "STOP",
            }
        ]
    }
    recorded = _install_recorder(monkeypatch, payload)

    result = llm_endpoint.complete("say hi", "gemini:m", max_tokens=50)

    assert len(recorded) == 1
    req = recorded[0]
    assert req.get_method() == "POST"
    url = _url(req)
    assert url == "https://generativelanguage.googleapis.com/v1beta/models/m:generateContent"
    assert GEMINI_KEY not in url
    assert "key=" not in url
    headers = _headers(req)
    assert headers.get("x-goog-api-key") == GEMINI_KEY
    assert headers.get("user-agent")
    body = _body(req)
    assert body["generationConfig"]["maxOutputTokens"] == 50
    assert "say hi" in json.dumps(body)

    assert field(result, "model_call_error") is None
    assert field(result, "text") == "hello from gemini"
    assert "internal musing" not in field(result, "text")
    assert field(result, "backend") == "gemini"


def test_ollama_wire_format(clean_env, monkeypatch):
    payload = {
        "model": "m",
        "created_at": "2026-01-01T00:00:00Z",
        "message": {"role": "assistant", "content": "ollama says hi"},
        "done": True,
    }
    recorded = _install_recorder(monkeypatch, payload)

    result = llm_endpoint.complete("say hi", "ollama:m", max_tokens=50)

    assert len(recorded) == 1
    req = recorded[0]
    assert req.get_method() == "POST"
    assert _url(req) == "http://localhost:11434/api/chat"
    headers = _headers(req)
    assert "authorization" not in headers
    assert headers.get("user-agent")
    body = _body(req)
    assert body["model"] == "m"
    assert body["stream"] is False
    assert body["options"]["num_predict"] == 50
    assert "say hi" in json.dumps(body)

    assert field(result, "model_call_error") is None
    assert field(result, "text") == "ollama says hi"
    assert field(result, "backend") == "ollama"


def test_openai_compatible_from_config_no_key(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.chdir(tmp_path)
    toml = (
        "[llm]\n"
        + "provider = " + json.dumps("openai-compatible") + "\n"
        + "model = " + json.dumps("m") + "\n"
        + "base_url = " + json.dumps("http://h:8000/v1") + "\n"
    )
    (tmp_path / "hotdocs.toml").write_text(toml, encoding="utf-8")

    payload = {
        "id": "chatcmpl-2",
        "object": "chat.completion",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": "compat hi"},
                "finish_reason": "stop",
            }
        ],
    }
    recorded = _install_recorder(monkeypatch, payload)

    result = llm_endpoint.complete("say hi", "m", max_tokens=50)

    assert len(recorded) == 1
    req = recorded[0]
    assert req.get_method() == "POST"
    assert _url(req) == "http://h:8000/v1/chat/completions"
    headers = _headers(req)
    assert "authorization" not in headers
    body = _body(req)
    assert body["max_tokens"] == 50
    assert "say hi" in json.dumps(body)

    assert field(result, "model_call_error") is None
    assert field(result, "text") == "compat hi"
    assert field(result, "backend") == "openai-compatible"