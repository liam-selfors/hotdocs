# hotdocs-criterion: sha256:bf9a0415aa15b0eb4a485c7ea7aa35a19e81610833474d5dabf59ab1fe140741
"""AC-ENDPOINT-008: each HTTP adapter speaks its provider's documented wire format."""

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

    def __exit__(self, *exc):
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
    return {k.lower(): v for k, v in request.header_items()}


def _body(request):
    data = request.data
    if isinstance(data, bytes):
        data = data.decode("utf-8")
    return json.loads(data)


def _isolate(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    for var in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY", "OLLAMA_API_KEY"):
        monkeypatch.delenv(var, raising=False)


ANTHROPIC_KEY = "sk-ant-test-key-123"
OPENAI_KEY = "sk-openai-test-key-456"
GEMINI_KEY = "gemini-test-key-789"

ANTHROPIC_REPLY = {
    "id": "msg_01",
    "type": "message",
    "role": "assistant",
    "model": "m",
    "content": [
        {"type": "thinking", "thinking": "Let me think.", "signature": "sig"},
        {"type": "text", "text": "hel"},
        {"type": "text", "text": "lo"},
    ],
    "stop_reason": "end_turn",
    "stop_sequence": None,
    "usage": {"input_tokens": 3, "output_tokens": 5},
}

OPENAI_REPLY = {
    "id": "chatcmpl-1",
    "object": "chat.completion",
    "created": 1700000000,
    "model": "m",
    "choices": [
        {
            "index": 0,
            "message": {"role": "assistant", "content": "hello"},
            "finish_reason": "stop",
        }
    ],
    "usage": {"prompt_tokens": 3, "completion_tokens": 1, "total_tokens": 4},
}

GEMINI_REPLY = {
    "candidates": [
        {
            "content": {
                "role": "model",
                "parts": [
                    {"text": "Thinking about greeting.", "thought": True},
                    {"text": "hello"},
                ],
            },
            "finishReason": "STOP",
            "index": 0,
        }
    ],
    "usageMetadata": {"promptTokenCount": 3, "candidatesTokenCount": 1, "totalTokenCount": 4},
}

OLLAMA_REPLY = {
    "model": "m",
    "created_at": "2026-01-01T00:00:00Z",
    "message": {"role": "assistant", "content": "hello"},
    "done": True,
}


def _check_anthropic(req):
    assert req.get_method() == "POST"
    assert req.full_url == "https://api.anthropic.com/v1/messages"
    h = _headers(req)
    assert h.get("x-api-key") == ANTHROPIC_KEY
    assert h.get("anthropic-version") == "2023-06-01"
    body = _body(req)
    assert body["model"] == "m"
    assert body["max_tokens"] == 50
    assert "say hi" in json.dumps(body["messages"])


def _check_openai(req):
    assert req.get_method() == "POST"
    assert req.full_url == "https://api.openai.com/v1/chat/completions"
    h = _headers(req)
    assert h.get("authorization") == "Bearer " + OPENAI_KEY
    body = _body(req)
    assert body["model"] == "m"
    assert body["max_completion_tokens"] == 50
    assert "say hi" in json.dumps(body["messages"])


def _check_gemini(req):
    assert req.get_method() == "POST"
    url = req.full_url
    assert url.split("?")[0] == (
        "https://generativelanguage.googleapis.com/v1beta/models/m:generateContent"
    )
    assert GEMINI_KEY not in url
    assert "key=" not in url
    h = _headers(req)
    assert h.get("x-goog-api-key") == GEMINI_KEY
    body = _body(req)
    assert body["generationConfig"]["maxOutputTokens"] == 50
    assert "say hi" in json.dumps(body["contents"])


def _check_ollama(req):
    assert req.get_method() == "POST"
    assert req.full_url == "http://localhost:11434/api/chat"
    h = _headers(req)
    assert "authorization" not in h
    body = _body(req)
    assert body["model"] == "m"
    assert body["stream"] is False
    assert body["options"]["num_predict"] == 50
    assert "say hi" in json.dumps(body["messages"])


CASES = [
    ("anthropic", "ANTHROPIC_API_KEY", ANTHROPIC_KEY, ANTHROPIC_REPLY, _check_anthropic, "hello"),
    ("openai", "OPENAI_API_KEY", OPENAI_KEY, OPENAI_REPLY, _check_openai, "hello"),
    ("gemini", "GEMINI_API_KEY", GEMINI_KEY, GEMINI_REPLY, _check_gemini, "hello"),
    ("ollama", None, None, OLLAMA_REPLY, _check_ollama, "hello"),
]


@pytest.mark.parametrize(
    "provider,key_var,key,reply,check,expected_text",
    CASES,
    ids=[c[0] for c in CASES],
)
def test_provider_wire_format(
    monkeypatch, tmp_path, provider, key_var, key, reply, check, expected_text
):
    _isolate(monkeypatch, tmp_path)
    if key_var is not None:
        monkeypatch.setenv(key_var, key)
    recorded = _install_recorder(monkeypatch, reply)

    model = provider + ":m"
    response = llm_endpoint.complete("say hi", model, max_tokens=50)

    assert len(recorded) == 1
    check(recorded[0])

    assert field(response, "model_call_error") is None
    assert field(response, "text") == expected_text
    assert field(response, "backend") == provider
    assert field(response, "model") == model


def test_openai_compatible_from_config_without_key(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    (tmp_path / "hotdocs.toml").write_text(
        "[llm]\n"
        + "provider = " + json.dumps("openai-compatible") + "\n"
        + "model = " + json.dumps("m") + "\n"
        + "base_url = " + json.dumps("http://h:8000/v1") + "\n",
        encoding="utf-8",
    )
    recorded = _install_recorder(monkeypatch, OPENAI_REPLY)

    response = llm_endpoint.complete("say hi", "m", max_tokens=50)

    assert len(recorded) == 1
    req = recorded[0]
    assert req.get_method() == "POST"
    assert req.full_url == "http://h:8000/v1/chat/completions"
    assert "authorization" not in _headers(req)
    body = _body(req)
    assert body["max_tokens"] == 50
    assert "say hi" in json.dumps(body["messages"])

    assert field(response, "model_call_error") is None
    assert field(response, "text") == "hello"
    assert field(response, "backend") == "openai-compatible"