# hotdocs-criterion: sha256:07c64df75d34670eca184bae922b24c54dac4e7d5024bbb8cf0f45b2b33c1e66
import email.message
import io
import socket
import urllib.error
import urllib.request

import pytest

import llm_endpoint


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


KEY_ENVS = ["ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY"]

HTTP_PROVIDERS = {
    "anthropic": "anthropic:claude-sonnet-5",
    "openai": "openai:gpt-6-astra",
    "openai-compatible": "openai-compatible:some-model",
    "gemini": "gemini:gemini-4-argon",
    "ollama": "ollama:llama3.2",
}

OPENAI_COMPATIBLE_TOML = (
    "[llm]\n"
    'provider = "openai-compatible"\n'
    'model = "some-model"\n'
    'base_url = "http://127.0.0.1:9/v1"\n'
)


def _http_error(code, body=b"{}"):
    return urllib.error.HTTPError(
        "http://example.invalid/",
        code,
        "error",
        email.message.Message(),
        io.BytesIO(body),
    )


class _UnreadableReply:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self, *args, **kwargs):
        return b"\x00\xff not json at all {"

    def close(self):
        pass


def _raise_http(code):
    def act():
        raise _http_error(code)
    return act


def _raise_timeout():
    raise socket.timeout("timed out")


def _raise_refused():
    raise urllib.error.URLError(ConnectionRefusedError(61, "Connection refused"))


def _return_unreadable():
    return _UnreadableReply()


OUTCOMES = [
    ("401", _raise_http(401), "auth"),
    ("403", _raise_http(403), "auth"),
    ("429", _raise_http(429), "rate_limit"),
    ("408", _raise_http(408), "timeout"),
    ("504", _raise_http(504), "timeout"),
    ("500", _raise_http(500), "network"),
    ("socket-timeout", _raise_timeout, "timeout"),
    ("refused", _raise_refused, "network"),
    ("unreadable-body", _return_unreadable, "network"),
]


def _prepare(monkeypatch, tmp_path, provider, with_keys=True):
    workdir = tmp_path / "work"
    workdir.mkdir()
    monkeypatch.chdir(workdir)
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    for name in KEY_ENVS:
        if with_keys:
            monkeypatch.setenv(name, "test-dummy-key-value")
        else:
            monkeypatch.delenv(name, raising=False)
    if provider == "openai-compatible":
        cfg = workdir / "hotdocs.toml"
        cfg.write_text(OPENAI_COMPATIBLE_TOML)
        monkeypatch.setenv("VAR_HOTDOCS_CONFIG", str(cfg))


def _install_recorder(monkeypatch, action):
    calls = []

    def recorder(request, *args, **kwargs):
        calls.append(request)
        return action()

    monkeypatch.setattr(urllib.request, "urlopen", recorder)
    return calls


@pytest.mark.parametrize("provider", sorted(HTTP_PROVIDERS))
@pytest.mark.parametrize(
    "label,action,expected", OUTCOMES, ids=[o[0] for o in OUTCOMES]
)
def test_http_failure_classified_once_without_raising(
    monkeypatch, tmp_path, provider, label, action, expected
):
    _prepare(monkeypatch, tmp_path, provider)
    calls = _install_recorder(monkeypatch, action)

    result = llm_endpoint.complete("Say hello.", HTTP_PROVIDERS[provider])

    err = field(result, "model_call_error")
    assert err is not None, (provider, label)
    assert field(err, "category") == expected, (provider, label)
    assert field(result, "text") is None
    assert len(calls) == 1, (provider, label, len(calls))


@pytest.mark.parametrize("provider", ["anthropic", "openai", "gemini"])
def test_missing_key_is_auth_without_call(monkeypatch, tmp_path, provider):
    _prepare(monkeypatch, tmp_path, provider, with_keys=False)
    calls = _install_recorder(monkeypatch, _raise_http(500))

    result = llm_endpoint.complete("Say hello.", HTTP_PROVIDERS[provider])

    err = field(result, "model_call_error")
    assert err is not None
    assert field(err, "category") == "auth"
    assert field(result, "text") is None
    assert calls == []


def test_gemini_400_invalid_api_key_is_auth(monkeypatch, tmp_path):
    _prepare(monkeypatch, tmp_path, "gemini")
    body = (
        b'{"error": {"code": 400, "message": "API key not valid. Please pass '
        b'a valid API key.", "status": "INVALID_ARGUMENT", "details": '
        b'[{"@type": "type.googleapis.com/google.rpc.ErrorInfo", '
        b'"reason": "API_KEY_INVALID", "domain": "googleapis.com"}]}}'
    )

    def action():
        raise _http_error(400, body)

    calls = _install_recorder(monkeypatch, action)

    result = llm_endpoint.complete("Say hello.", HTTP_PROVIDERS["gemini"])

    err = field(result, "model_call_error")
    assert err is not None
    assert field(err, "category") == "auth"
    assert field(result, "text") is None
    assert len(calls) == 1