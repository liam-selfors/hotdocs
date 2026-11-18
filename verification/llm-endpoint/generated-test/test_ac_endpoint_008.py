# hotdocs-criterion: sha256:d372593334530003f8b86b1cc881c05c1daa16d80e20b69409add4c73de5a85b
import json
import urllib.request

import pytest

import llm_endpoint


PROMPT = "say hi"

KEYS = {
    "ANTHROPIC_API_KEY": "sk-ant-test-key-AAA111",
    "OPENAI_API_KEY": "sk-openai-test-key-BBB222",
    "GEMINI_API_KEY": "gemini-test-key-CCC333",
}


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


class _FakeReply:
    def __init__(self, payload):
        self._body = json.dumps(payload).encode("utf-8")
        self.status = 200
        self.code = 200

    def read(self, *args, **kwargs):
        return self._body

    def getcode(self):
        return 200

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def _snapshot(request):
    if isinstance(request, str):
        return {"method": "GET", "url": request, "headers": {}, "body": None}
    method = request.get_method()
    url = request.full_url
    headers = {k.lower(): v for k, v in request.header_items()}
    data = request.data
    body = None
    if data is not None:
        if isinstance(data, (bytes, bytearray)):
            data = data.decode("utf-8")
        body = json.loads(data)
    return {"method": method, "url": url, "headers": headers, "body": body}


def _install_recorder(monkeypatch, reply_payload):
    recorded = []

    def fake_urlopen(request, *args, **kwargs):
        recorded.append(_snapshot(request))
        return _FakeReply(reply_payload)

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    return recorded


@pytest.fixture
def clean_env(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    monkeypatch.chdir(tmp_path)
    for name in KEYS:
        monkeypatch.delenv(name, raising=False)
    return tmp_path


ANTHROPIC_REPLY = {
    "id": "msg_01",
    "type": "message",
    "role": "assistant",
    "model": "m",
    "content": [
        {"type": "thinking", "thinking": "SECRET-THOUGHTS", "signature": "sig"},
        {"type": "text", "text": "Hello"},
        {"type": "text", "text": " there"},
    ],
    "stop_reason": "end_turn",
    "stop_sequence": None,
    "usage": {"input_tokens": 3, "output_tokens": 4},
}

OPENAI_REPLY = {
    "id": "chatcmpl-1",
    "object": "chat.completion",
    "created": 1700000000,
    "model": "m",
    "choices": [
        {
            "index": 0,
            "message": {"role": "assistant", "content": "Hi from openai"},
            "finish_reason": "stop",
        }
    ],
    "usage": {"prompt_tokens": 3, "completion_tokens": 4, "total_tokens": 7},
}

GEMINI_REPLY = {
    "candidates": [
        {
            "content": {
                "role": "model",
                "parts": [
                    {"text": "SECRET-THOUGHTS", "thought": True},
                    {"text": "Hi from gemini"},
                ],
            },
            "finishReason": "STOP",
            "index": 0,
        }
    ],
    "usageMetadata": {"promptTokenCount": 3, "candidatesTokenCount": 4},
}

OLLAMA_REPLY = {
    "model": "m",
    "created_at": "2026-01-01T00:00:00Z",
    "message": {"role": "assistant", "content": "Hi from ollama"},
    "done": True,
}


def _common_success_checks(resp, recorded):
    assert field(resp, "model_call_error") is None
    assert len(recorded) == 1, recorded
    req = recorded[0]
    assert req["method"] == "POST"
    ua = req["headers"].get("user-agent")
    assert ua, "a descriptive User-Agent header must be sent"
    assert req["body"] is not None
    assert PROMPT in json.dumps(req["body"])
    return req


def test_anthropic_wire_format(clean_env, monkeypatch):
    for k, v in KEYS.items():
        monkeypatch.setenv(k, v)
    recorded = _install_recorder(monkeypatch, ANTHROPIC_REPLY)

    resp = llm_endpoint.complete(PROMPT, "anthropic:m", max_tokens=50)
    req = _common_success_checks(resp, recorded)

    assert req["url"] == "https://api.anthropic.com/v1/messages"
    assert req["headers"].get("x-api-key") == KEYS["ANTHROPIC_API_KEY"]
    assert req["headers"].get("anthropic-version") == "2023-06-01"
    assert "authorization" not in req["headers"]
    body = req["body"]
    assert body["max_tokens"] == 50
    assert body["model"] == "m"
    assert PROMPT in json.dumps(body["messages"])

    text = field(resp, "text")
    assert text in ("Hello there", "Hello\n there")
    assert "SECRET-THOUGHTS" not in text


def test_openai_wire_format(clean_env, monkeypatch):
    for k, v in KEYS.items():
        monkeypatch.setenv(k, v)
    recorded = _install_recorder(monkeypatch, OPENAI_REPLY)

    resp = llm_endpoint.complete(PROMPT, "openai:m", max_tokens=50)
    req = _common_success_checks(resp, recorded)

    assert req["url"] == "https://api.openai.com/v1/chat/completions"
    assert req["headers"].get("authorization") == "Bearer " + KEYS["OPENAI_API_KEY"]
    body = req["body"]
    assert body["max_completion_tokens"] == 50
    assert "max_tokens" not in body
    assert body["model"] == "m"
    assert PROMPT in json.dumps(body["messages"])

    assert field(resp, "text") == "Hi from openai"


def test_gemini_wire_format(clean_env, monkeypatch):
    for k, v in KEYS.items():
        monkeypatch.setenv(k, v)
    recorded = _install_recorder(monkeypatch, GEMINI_REPLY)

    resp = llm_endpoint.complete(PROMPT, "gemini:m", max_tokens=50)
    req = _common_success_checks(resp, recorded)

    url = req["url"]
    assert url == "https://generativelanguage.googleapis.com/v1beta/models/m:generateContent"
    assert KEYS["GEMINI_API_KEY"] not in url
    assert "key=" not in url
    assert req["headers"].get("x-goog-api-key") == KEYS["GEMINI_API_KEY"]
    body = req["body"]
    assert body["generationConfig"]["maxOutputTokens"] == 50
    assert PROMPT in json.dumps(body["contents"])

    text = field(resp, "text")
    assert text == "Hi from gemini"
    assert "SECRET-THOUGHTS" not in text


def test_ollama_wire_format(clean_env, monkeypatch):
    for k, v in KEYS.items():
        monkeypatch.setenv(k, v)
    recorded = _install_recorder(monkeypatch, OLLAMA_REPLY)

    resp = llm_endpoint.complete(PROMPT, "ollama:m", max_tokens=50)
    req = _common_success_checks(resp, recorded)

    assert req["url"] == "http://localhost:11434/api/chat"
    assert "authorization" not in req["headers"]
    assert "x-api-key" not in req["headers"]
    body = req["body"]
    assert body["stream"] is False
    assert body["options"]["num_predict"] == 50
    assert body["model"] == "m"
    assert PROMPT in json.dumps(body["messages"])

    assert field(resp, "text") == "Hi from ollama"


def test_openai_compatible_from_config_without_key(clean_env, monkeypatch):
    (clean_env / "hotdocs.toml").write_text(
        "[llm]\n"
        'provider = "openai-compatible"\n'
        'model = "m"\n'
        'base_url = "http://h:8000/v1"\n',
        encoding="utf-8",
    )
    recorded = _install_recorder(monkeypatch, OPENAI_REPLY)

    resp = llm_endpoint.complete(PROMPT, "m", max_tokens=50)
    req = _common_success_checks(resp, recorded)

    assert req["url"] == "http://h:8000/v1/chat/completions"
    assert "authorization" not in req["headers"]
    body = req["body"]
    assert body["max_tokens"] == 50
    assert body["model"] == "m"

    assert field(resp, "text") == "Hi from openai"