# hotdocs-criterion: sha256:1933250a290d4c1e6e959315277aa6a0fb40fcf60114f13f63af0a2f089c9e9c
import email.message
import io
import json
import socket
import urllib.error
import urllib.request

import pytest

import llm_endpoint


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


KEY_ENVS = ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY")

HTTP_PROVIDERS = {
    "anthropic": ("anthropic:claude-sonnet-5", "ANTHROPIC_API_KEY"),
    "openai": ("openai:gpt-6-astra", "OPENAI_API_KEY"),
    "openai-compatible": ("compat-model", None),
    "gemini": ("gemini:gemini-4-argon", "GEMINI_API_KEY"),
    "ollama": ("ollama:llama3.2", None),
}


def _http_error(code, body=b"{}"):
    return urllib.error.HTTPError(
        "http://example.invalid/", code, "error", email.message.Message(), io.BytesIO(body)
    )


class _UnreadableReply:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self, *args, **kwargs):
        return b"\xff\xfe this is not json {{{"

    def close(self):
        pass


def _fail_401():
    raise _http_error(401)


def _fail_403():
    raise _http_error(403)


def _fail_429():
    raise _http_error(429)


def _fail_408():
    raise _http_error(408)


def _fail_504():
    raise _http_error(504)


def _fail_500():
    raise _http_error(500)


def _fail_socket_timeout():
    raise socket.timeout("timed out")


def _fail_refused():
    raise urllib.error.URLError(ConnectionRefusedError(61, "Connection refused"))


def _unreadable():
    return _UnreadableReply()


CASES = [
    ("401", _fail_401, "auth"),
    ("403", _fail_403, "auth"),
    ("429", _fail_429, "rate_limit"),
    ("408", _fail_408, "timeout"),
    ("504", _fail_504, "timeout"),
    ("500", _fail_500, "network"),
    ("socket_timeout", _fail_socket_timeout, "timeout"),
    ("refused", _fail_refused, "network"),
    ("unreadable_body", _unreadable, "network"),
]


def _setup(monkeypatch, tmp_path, provider, with_keys=True):
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    monkeypatch.chdir(tmp_path)
    for name in KEY_ENVS:
        if with_keys:
            monkeypatch.setenv(name, "test-key-value-123")
        else:
            monkeypatch.delenv(name, raising=False)
    if provider == "openai-compatible":
        llm_endpoint.save_config(
            tmp_path / "hotdocs.toml",
            "openai-compatible",
            "compat-model",
            base_url="http://localhost:9/v1",
        )


def _install_recorder(monkeypatch, behavior):
    calls = []

    def recorder(request, *args, **kwargs):
        calls.append(request)
        return behavior()

    monkeypatch.setattr(urllib.request, "urlopen", recorder)
    return calls


def _assert_error(result, category):
    err = field(result, "model_call_error")
    assert err is not None
    assert field(err, "category") == category
    assert field(result, "text") is None


@pytest.mark.parametrize("provider", sorted(HTTP_PROVIDERS))
@pytest.mark.parametrize("label,behavior,category", CASES, ids=[c[0] for c in CASES])
def test_http_failure_classification(monkeypatch, tmp_path, provider, label, behavior, category):
    _setup(monkeypatch, tmp_path, provider)
    calls = _install_recorder(monkeypatch, behavior)
    model, _ = HTTP_PROVIDERS[provider]

    result = llm_endpoint.complete("Say hello.", model)

    _assert_error(result, category)
    assert len(calls) == 1


@pytest.mark.parametrize(
    "provider", sorted(p for p, (_, key) in HTTP_PROVIDERS.items() if key is not None)
)
def test_missing_key_reports_auth_without_call(monkeypatch, tmp_path, provider):
    _setup(monkeypatch, tmp_path, provider, with_keys=False)

    def behavior():
        raise AssertionError("urlopen must not be called")

    calls = _install_recorder(monkeypatch, behavior)
    model, _ = HTTP_PROVIDERS[provider]

    result = llm_endpoint.complete("Say hello.", model)

    _assert_error(result, "auth")
    assert calls == []


def test_gemini_400_invalid_api_key_is_auth(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path, "gemini")
    body = json.dumps(
        {
            "error": {
                "code": 400,
                "message": "API key not valid. Please pass a valid API key.",
                "status": "INVALID_ARGUMENT",
                "details": [
                    {
                        "@type": "type.googleapis.com/google.rpc.ErrorInfo",
                        "reason": "API_KEY_INVALID",
                        "domain": "googleapis.com",
                    }
                ],
            }
        }
    ).encode("utf-8")

    def behavior():
        raise _http_error(400, body)

    calls = _install_recorder(monkeypatch, behavior)

    result = llm_endpoint.complete("Say hello.", "gemini:gemini-4-argon")

    _assert_error(result, "auth")
    assert len(calls) == 1