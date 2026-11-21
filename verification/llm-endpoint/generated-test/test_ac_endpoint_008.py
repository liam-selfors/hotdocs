# hotdocs-criterion: sha256:1297a172daf79e570d84049010d4ad880c3ec6b5f36cdd0c888f9a5c27c7dfd7
import json
import urllib.request

import pytest

import llm_endpoint


KEYS = {
    "ANTHROPIC_API_KEY": "sk-ant-test-key-123",
    "OPENAI_API_KEY": "sk-openai-test-key-456",
    "GEMINI_API_KEY": "gemini-test-key-789",
}


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


class FakeReply:
    def __init__(self, payload):
        self._data = json.dumps(payload).encode("utf-8")

    def read(self, *args, **kwargs):
        return self._data

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def install_recorder(monkeypatch, payload):
    calls = []

    def fake_urlopen(request, data=None, timeout=None, *args, **kwargs):
        calls.append({"request": request, "timeout": timeout})
        return FakeReply(payload)

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    return calls


def request_parts(request):
    assert isinstance(request, urllib.request.Request)
    headers = {k.lower(): v for k, v in request.header_items()}
    raw = request.data
    if isinstance(raw, (bytes, bytearray)):
        raw = raw.decode("utf-8")
    body = json.loads(raw) if raw else None
    return request.get_method(), request.full_url, headers, body


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    monkeypatch.chdir(tmp_path)
    return tmp_path


ANTHROPIC_REPLY = {
    "id": "msg_1",
    "type": "message",
    "role": "assistant",
    "model": "m",
    "content": [
        {"type": "thinking", "thinking": "let me think", "signature": "sig"},
        {"type": "text", "text": "Hello"},
        {"type": "text", "text": " world"},
    ],
    "stop_reason": "end_turn",
    "usage": {"input_tokens": 3, "output_tokens": 2},
}

OPENAI_REPLY = {
    "id": "chatcmpl-1",
    "object": "chat.completion",
    "model": "m",
    "choices": [
        {
            "index": 0,
            "message": {"role": "assistant", "content": "Hi from openai"},
            "finish_reason": "stop",
        }
    ],
}

GEMINI_REPLY = {
    "candidates": [
        {
            "content": {
                "role": "model",
                "parts": [
                    {"text": "internal musing", "thought": True},
                    {"text": "Hi"},
                    {"text": " there"},
                ],
            },
            "finishReason": "STOP",
        }
    ]
}

OLLAMA_REPLY = {
    "model": "m",
    "created_at": "2026-01-01T00:00:00Z",
    "message": {"role": "assistant", "content": "Hi from ollama"},
    "done": True,
}


def check_common(resp, provider, model_string, expected_text, headers):
    assert field(resp, "model_call_error") is None
    assert field(resp, "text") == expected_text
    assert field(resp, "backend") == provider
    assert field(resp, "model") == model_string
    assert headers.get("user-agent"), "a descriptive User-Agent is required"


def test_anthropic_wire_format(isolated, monkeypatch):
    for k, v in KEYS.items():
        monkeypatch.setenv(k, v)
    calls = install_recorder(monkeypatch, ANTHROPIC_REPLY)

    resp = llm_endpoint.complete("say hi", "anthropic:m", max_tokens=50)

    assert len(calls) == 1
    method, url, headers, body = request_parts(calls[0]["request"])
    assert method == "POST"
    assert url == "https://api.anthropic.com/v1/messages"
    assert headers.get("x-api-key") == KEYS["ANTHROPIC_API_KEY"]
    assert headers.get("anthropic-version") == "2023-06-01"
    assert "authorization" not in headers
    assert body["model"] == "m"
    assert body["max_tokens"] == 50
    assert "say hi" in json.dumps(body["messages"])
    check_common(resp, "anthropic", "anthropic:m", "Hello world", headers)


def test_openai_wire_format(isolated, monkeypatch):
    for k, v in KEYS.items():
        monkeypatch.setenv(k, v)
    calls = install_recorder(monkeypatch, OPENAI_REPLY)

    resp = llm_endpoint.complete("say hi", "openai:m", max_tokens=50)

    assert len(calls) == 1
    method, url, headers, body = request_parts(calls[0]["request"])
    assert method == "POST"
    assert url == "https://api.openai.com/v1/chat/completions"
    assert headers.get("authorization") == "Bearer " + KEYS["OPENAI_API_KEY"]
    assert body["model"] == "m"
    assert body["max_completion_tokens"] == 50
    assert "max_tokens" not in body
    assert "say hi" in json.dumps(body["messages"])
    check_common(resp, "openai", "openai:m", "Hi from openai", headers)


def test_gemini_wire_format(isolated, monkeypatch):
    for k, v in KEYS.items():
        monkeypatch.setenv(k, v)
    calls = install_recorder(monkeypatch, GEMINI_REPLY)

    resp = llm_endpoint.complete("say hi", "gemini:m", max_tokens=50)

    assert len(calls) == 1
    method, url, headers, body = request_parts(calls[0]["request"])
    assert method == "POST"
    assert url == (
        "https://generativelanguage.googleapis.com/v1beta/models/m:generateContent"
    )
    assert headers.get("x-goog-api-key") == KEYS["GEMINI_API_KEY"]
    assert KEYS["GEMINI_API_KEY"] not in url
    assert "key=" not in url
    assert body["generationConfig"]["maxOutputTokens"] == 50
    assert "say hi" in json.dumps(body["contents"])
    check_common(resp, "gemini", "gemini:m", "Hi there", headers)


def test_ollama_wire_format(isolated, monkeypatch):
    for k, v in KEYS.items():
        monkeypatch.setenv(k, v)
    calls = install_recorder(monkeypatch, OLLAMA_REPLY)

    resp = llm_endpoint.complete("say hi", "ollama:m", max_tokens=50)

    assert len(calls) == 1
    method, url, headers, body = request_parts(calls[0]["request"])
    assert method == "POST"
    assert url == "http://localhost:11434/api/chat"
    assert "authorization" not in headers
    assert body["model"] == "m"
    assert body["stream"] is False
    assert body["options"]["num_predict"] == 50
    assert "say hi" in json.dumps(body["messages"])
    check_common(resp, "ollama", "ollama:m", "Hi from ollama", headers)


def test_openai_compatible_from_config_without_key(isolated, monkeypatch):
    for k in KEYS:
        monkeypatch.delenv(k, raising=False)
    toml = (
        "[llm]\n"
        + "provider = " + json.dumps("openai-compatible") + "\n"
        + "model = " + json.dumps("m") + "\n"
        + "base_url = " + json.dumps("http://h:8000/v1") + "\n"
    )
    (isolated / "hotdocs.toml").write_text(toml, encoding="utf-8")
    calls = install_recorder(monkeypatch, OPENAI_REPLY)

    resp = llm_endpoint.complete("say hi", "m", max_tokens=50)

    assert len(calls) == 1
    method, url, headers, body = request_parts(calls[0]["request"])
    assert method == "POST"
    assert url == "http://h:8000/v1/chat/completions"
    assert "authorization" not in headers
    assert body["max_tokens"] == 50
    assert body["model"] == "m"
    assert field(resp, "model_call_error") is None
    assert field(resp, "text") == "Hi from openai"
    assert field(resp, "backend") == "openai-compatible"
    assert field(resp, "model") == "m"