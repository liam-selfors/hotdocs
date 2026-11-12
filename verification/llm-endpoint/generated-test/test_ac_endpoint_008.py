import json
import urllib.parse
import urllib.request

import pytest

import llm_endpoint


ANTHROPIC_KEY = "sk-ant-test-key-aaaa1111"
OPENAI_KEY = "sk-openai-test-key-bbbb2222"
GEMINI_KEY = "gemini-test-key-cccc3333"


def _field(value, name):
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


class _FakeReply:
    def __init__(self, payload):
        self._body = json.dumps(payload).encode("utf-8")
        self.status = 200
        self.code = 200

    def read(self, *args, **kwargs):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def getcode(self):
        return 200


class _Recorder:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def __call__(self, request, *args, **kwargs):
        self.calls.append(request)
        return _FakeReply(self.payload)


def _headers(request):
    out = {}
    try:
        items = request.header_items()
    except Exception:
        items = []
        items.extend(getattr(request, "headers", {}).items())
        items.extend(getattr(request, "unredirected_hdrs", {}).items())
    for k, v in items:
        out[str(k).lower()] = v
    return out


def _body(request):
    data = getattr(request, "data", None)
    assert data is not None, "request has no body"
    if isinstance(data, (bytes, bytearray)):
        data = data.decode("utf-8")
    return json.loads(data)


def _method(request):
    return request.get_method()


def _url(request):
    return request.full_url


def _main_requests(recorder):
    reqs = []
    for r in recorder.calls:
        assert isinstance(r, urllib.request.Request), (
            "urlopen must be called with a urllib.request.Request"
        )
        if _url(r).rstrip("/").endswith("/api/tags"):
            continue
        reqs.append(r)
    return reqs


@pytest.fixture
def clean_env(tmp_path, monkeypatch):
    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.chdir(work)
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", ANTHROPIC_KEY)
    monkeypatch.setenv("OPENAI_API_KEY", OPENAI_KEY)
    monkeypatch.setenv("GEMINI_API_KEY", GEMINI_KEY)
    return work


def _check_user_agent(headers):
    ua = headers.get("user-agent")
    assert ua, "a descriptive User-Agent header must be sent"
    assert not str(ua).startswith("Python-urllib"), ua


def _check_response_ok(resp, model_id, backend, expected_text=None):
    err = _field(resp, "model_call_error")
    assert err is None, f"unexpected model_call_error: {err!r}"
    assert _field(resp, "model") == model_id
    assert _field(resp, "backend") == backend
    text = _field(resp, "text")
    assert isinstance(text, str)
    if expected_text is not None:
        assert text == expected_text
    return text


def test_anthropic_wire_format(clean_env, monkeypatch):
    reply = {
        "id": "msg_01",
        "type": "message",
        "role": "assistant",
        "model": "m",
        "content": [
            {"type": "thinking", "thinking": "SECRET-THOUGHTS", "signature": "sig"},
            {"type": "text", "text": "Hello"},
            {"type": "text", "text": "world"},
        ],
        "stop_reason": "end_turn",
        "stop_sequence": None,
        "usage": {"input_tokens": 3, "output_tokens": 2},
    }
    rec = _Recorder(reply)
    monkeypatch.setattr(urllib.request, "urlopen", rec)

    resp = llm_endpoint.complete("say hi", "anthropic:m", max_tokens=50)

    reqs = _main_requests(rec)
    assert len(reqs) == 1, [_url(r) for r in reqs]
    req = reqs[0]
    assert _method(req) == "POST"
    assert _url(req) == "https://api.anthropic.com/v1/messages"
    headers = _headers(req)
    assert headers.get("x-api-key") == ANTHROPIC_KEY
    assert headers.get("anthropic-version") == "2023-06-01"
    _check_user_agent(headers)
    body = _body(req)
    assert body.get("max_tokens") == 50
    assert body.get("model") == "m"
    assert "say hi" in json.dumps(body.get("messages"))

    text = _check_response_ok(resp, "anthropic:m", "anthropic")
    assert "SECRET-THOUGHTS" not in text
    assert "".join(text.split()) == "Helloworld"
    assert text.index("Hello") < text.index("world")


def test_openai_wire_format(clean_env, monkeypatch):
    reply = {
        "id": "chatcmpl-1",
        "object": "chat.completion",
        "created": 1700000000,
        "model": "m",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": "hi from openai"},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 3, "completion_tokens": 3, "total_tokens": 6},
    }
    rec = _Recorder(reply)
    monkeypatch.setattr(urllib.request, "urlopen", rec)

    resp = llm_endpoint.complete("say hi", "openai:m", max_tokens=50)

    reqs = _main_requests(rec)
    assert len(reqs) == 1, [_url(r) for r in reqs]
    req = reqs[0]
    assert _method(req) == "POST"
    assert _url(req) == "https://api.openai.com/v1/chat/completions"
    headers = _headers(req)
    assert headers.get("authorization") == f"Bearer {OPENAI_KEY}"
    _check_user_agent(headers)
    body = _body(req)
    assert body.get("max_completion_tokens") == 50
    assert "max_tokens" not in body
    assert body.get("model") == "m"
    assert "say hi" in json.dumps(body.get("messages"))

    _check_response_ok(resp, "openai:m", "openai", "hi from openai")


def test_gemini_wire_format(clean_env, monkeypatch):
    reply = {
        "candidates": [
            {
                "content": {
                    "role": "model",
                    "parts": [
                        {"text": "SECRET-THOUGHTS", "thought": True},
                        {"text": "hi from gemini"},
                    ],
                },
                "finishReason": "STOP",
                "index": 0,
            }
        ],
        "usageMetadata": {"promptTokenCount": 3, "candidatesTokenCount": 3},
    }
    rec = _Recorder(reply)
    monkeypatch.setattr(urllib.request, "urlopen", rec)

    resp = llm_endpoint.complete("say hi", "gemini:m", max_tokens=50)

    reqs = _main_requests(rec)
    assert len(reqs) == 1, [_url(r) for r in reqs]
    req = reqs[0]
    assert _method(req) == "POST"
    url = _url(req)
    assert url == (
        "https://generativelanguage.googleapis.com/v1beta/models/m:generateContent"
    )
    assert GEMINI_KEY not in url
    query = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
    assert "key" not in query
    headers = _headers(req)
    assert headers.get("x-goog-api-key") == GEMINI_KEY
    _check_user_agent(headers)
    body = _body(req)
    gen_cfg = body.get("generationConfig")
    assert isinstance(gen_cfg, dict)
    assert gen_cfg.get("maxOutputTokens") == 50
    assert "say hi" in json.dumps(body.get("contents"))

    text = _check_response_ok(resp, "gemini:m", "gemini", "hi from gemini")
    assert "SECRET-THOUGHTS" not in text


def test_ollama_wire_format(clean_env, monkeypatch):
    reply = {
        "model": "m",
        "created_at": "2026-01-01T00:00:00Z",
        "message": {"role": "assistant", "content": "hi from ollama"},
        "done": True,
        "done_reason": "stop",
    }
    rec = _Recorder(reply)
    monkeypatch.setattr(urllib.request, "urlopen", rec)

    resp = llm_endpoint.complete("say hi", "ollama:m", max_tokens=50)

    reqs = _main_requests(rec)
    assert len(reqs) == 1, [_url(r) for r in reqs]
    req = reqs[0]
    assert _method(req) == "POST"
    assert _url(req) == "http://localhost:11434/api/chat"
    headers = _headers(req)
    assert "authorization" not in headers
    _check_user_agent(headers)
    body = _body(req)
    assert body.get("stream") is False
    options = body.get("options")
    assert isinstance(options, dict)
    assert options.get("num_predict") == 50
    assert body.get("model") == "m"
    assert "say hi" in json.dumps(body.get("messages"))

    _check_response_ok(resp, "ollama:m", "ollama", "hi from ollama")


def test_openai_compatible_from_config_without_key(tmp_path, monkeypatch):
    work = tmp_path / "work"
    work.mkdir()
    (work / "hotdocs.toml").write_text(
        "[llm]\n"
        'provider = "openai-compatible"\n'
        'model = "m"\n'
        'base_url = "http://h:8000/v1"\n',
        encoding="utf-8",
    )
    monkeypatch.chdir(work)
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    reply = {
        "id": "chatcmpl-2",
        "object": "chat.completion",
        "model": "m",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": "hi from compat"},
                "finish_reason": "stop",
            }
        ],
    }
    rec = _Recorder(reply)
    monkeypatch.setattr(urllib.request, "urlopen", rec)

    resp = llm_endpoint.complete("say hi", "m", max_tokens=50)

    reqs = _main_requests(rec)
    assert len(reqs) == 1, [_url(r) for r in reqs]
    req = reqs[0]
    assert _method(req) == "POST"
    assert _url(req) == "http://h:8000/v1/chat/completions"
    headers = _headers(req)
    assert "authorization" not in headers
    body = _body(req)
    assert body.get("max_tokens") == 50
    assert body.get("model") == "m"

    _check_response_ok(resp, "m", "openai-compatible", "hi from compat")