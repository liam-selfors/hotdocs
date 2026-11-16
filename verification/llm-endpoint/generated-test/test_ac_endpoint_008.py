import json
import urllib.request

import pytest

import llm_endpoint


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


class _FakeReply:
    def __init__(self, payload):
        self._data = json.dumps(payload).encode("utf-8")
        self.status = 200
        self.code = 200
        self.headers = {"Content-Type": "application/json"}

    def read(self, *args, **kwargs):
        return self._data

    def getcode(self):
        return 200

    def info(self):
        return self.headers

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _Recorder:
    def __init__(self, payload):
        self.payload = payload
        self.requests = []

    def __call__(self, request, *args, **kwargs):
        self.requests.append(request)
        return _FakeReply(self.payload)


def _headers(request):
    items = {}
    for name, value in request.header_items():
        items[name.lower()] = value
    return items


def _url(request):
    return request.full_url if isinstance(request, urllib.request.Request) else str(request)


def _body(request):
    data = request.data
    assert data is not None, "request carries no body"
    if isinstance(data, (bytes, bytearray)):
        data = data.decode("utf-8")
    return json.loads(data)


def _find_request(recorder, expected_url):
    urls = [_url(r) for r in recorder.requests]
    matching = [r for r in recorder.requests if _url(r) == expected_url]
    assert len(matching) == 1, f"expected exactly one request to {expected_url}, saw {urls}"
    return matching[0]


def _assert_user_agent(headers):
    ua = headers.get("user-agent")
    assert ua, "no User-Agent header set on the request"
    assert not ua.startswith("Python-urllib"), f"User-Agent is not descriptive: {ua!r}"


@pytest.fixture
def clean_env(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    workdir = tmp_path / "work"
    workdir.mkdir()
    monkeypatch.chdir(workdir)
    return workdir


ANTHROPIC_KEY = "sk-ant-test-key-1111"
OPENAI_KEY = "sk-openai-test-key-2222"
GEMINI_KEY = "gemini-test-key-3333"


def test_anthropic_wire_format(clean_env, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", ANTHROPIC_KEY)
    reply = {
        "id": "msg_1",
        "type": "message",
        "role": "assistant",
        "model": "m",
        "content": [
            {"type": "thinking", "thinking": "SECRET-THOUGHTS", "signature": "sig"},
            {"type": "text", "text": "Hello"},
            {"type": "text", "text": "world"},
        ],
        "stop_reason": "end_turn",
        "usage": {"input_tokens": 3, "output_tokens": 2},
    }
    recorder = _Recorder(reply)
    monkeypatch.setattr(urllib.request, "urlopen", recorder)

    result = llm_endpoint.complete("say hi", "anthropic:m", max_tokens=50)

    req = _find_request(recorder, "https://api.anthropic.com/v1/messages")
    assert req.get_method() == "POST"
    headers = _headers(req)
    assert headers.get("x-api-key") == ANTHROPIC_KEY
    assert headers.get("anthropic-version") == "2023-06-01"
    assert "authorization" not in headers
    _assert_user_agent(headers)
    body = _body(req)
    assert body["max_tokens"] == 50
    assert body["model"] == "m"
    assert "say hi" in json.dumps(body["messages"])

    assert field(result, "model_call_error") is None
    text = field(result, "text")
    assert isinstance(text, str)
    assert "SECRET-THOUGHTS" not in text
    assert text.startswith("Hello")
    assert text.endswith("world")
    assert text[len("Hello"):-len("world")].strip() == ""
    assert field(result, "model") == "anthropic:m"
    assert field(result, "backend") == "anthropic"


def test_openai_wire_format(clean_env, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", OPENAI_KEY)
    reply = {
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
        "usage": {"prompt_tokens": 3, "completion_tokens": 3, "total_tokens": 6},
    }
    recorder = _Recorder(reply)
    monkeypatch.setattr(urllib.request, "urlopen", recorder)

    result = llm_endpoint.complete("say hi", "openai:m", max_tokens=50)

    req = _find_request(recorder, "https://api.openai.com/v1/chat/completions")
    assert req.get_method() == "POST"
    headers = _headers(req)
    assert headers.get("authorization") == f"Bearer {OPENAI_KEY}"
    _assert_user_agent(headers)
    body = _body(req)
    assert body["max_completion_tokens"] == 50
    assert "max_tokens" not in body
    assert body["model"] == "m"
    assert "say hi" in json.dumps(body["messages"])

    assert field(result, "model_call_error") is None
    assert field(result, "text") == "Hi from openai"
    assert field(result, "model") == "openai:m"
    assert field(result, "backend") == "openai"


def test_gemini_wire_format(clean_env, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", GEMINI_KEY)
    reply = {
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
        "usageMetadata": {"promptTokenCount": 3, "candidatesTokenCount": 3},
    }
    recorder = _Recorder(reply)
    monkeypatch.setattr(urllib.request, "urlopen", recorder)

    result = llm_endpoint.complete("say hi", "gemini:m", max_tokens=50)

    expected_url = "https://generativelanguage.googleapis.com/v1beta/models/m:generateContent"
    for r in recorder.requests:
        assert GEMINI_KEY not in _url(r), "Gemini key leaked into the URL"
        assert "key=" not in _url(r), "Gemini key passed as a URL query parameter"
    req = _find_request(recorder, expected_url)
    assert req.get_method() == "POST"
    headers = _headers(req)
    assert headers.get("x-goog-api-key") == GEMINI_KEY
    assert "authorization" not in headers
    _assert_user_agent(headers)
    body = _body(req)
    assert body["generationConfig"]["maxOutputTokens"] == 50
    assert "say hi" in json.dumps(body["contents"])

    assert field(result, "model_call_error") is None
    assert field(result, "text") == "Hi from gemini"
    assert field(result, "model") == "gemini:m"
    assert field(result, "backend") == "gemini"


def test_ollama_wire_format(clean_env, monkeypatch):
    reply = {
        "model": "m",
        "created_at": "2026-01-01T00:00:00Z",
        "message": {"role": "assistant", "content": "Hi from ollama"},
        "done": True,
    }
    recorder = _Recorder(reply)
    monkeypatch.setattr(urllib.request, "urlopen", recorder)

    result = llm_endpoint.complete("say hi", "ollama:m", max_tokens=50)

    req = _find_request(recorder, "http://localhost:11434/api/chat")
    assert req.get_method() == "POST"
    headers = _headers(req)
    assert "authorization" not in headers
    _assert_user_agent(headers)
    body = _body(req)
    assert body["stream"] is False
    assert body["options"]["num_predict"] == 50
    assert body["model"] == "m"
    assert "say hi" in json.dumps(body["messages"])

    assert field(result, "model_call_error") is None
    assert field(result, "text") == "Hi from ollama"
    assert field(result, "model") == "ollama:m"
    assert field(result, "backend") == "ollama"


def test_openai_compatible_from_config_without_key(clean_env, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    (clean_env / "hotdocs.toml").write_text(
        "[llm]\n"
        'provider = "openai-compatible"\n'
        'model = "m"\n'
        'base_url = "http://h:8000/v1"\n',
        encoding="utf-8",
    )
    reply = {
        "id": "chatcmpl-2",
        "object": "chat.completion",
        "model": "m",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": "Hi from compat"},
                "finish_reason": "stop",
            }
        ],
    }
    recorder = _Recorder(reply)
    monkeypatch.setattr(urllib.request, "urlopen", recorder)

    result = llm_endpoint.complete("say hi", "m", max_tokens=50)

    req = _find_request(recorder, "http://h:8000/v1/chat/completions")
    assert req.get_method() == "POST"
    headers = _headers(req)
    assert "authorization" not in headers
    body = _body(req)
    assert body["max_tokens"] == 50
    assert body["model"] == "m"

    assert field(result, "model_call_error") is None
    assert field(result, "text") == "Hi from compat"
    assert field(result, "backend") == "openai-compatible"