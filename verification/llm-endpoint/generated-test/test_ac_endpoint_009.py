# hotdocs-criterion: sha256:cd6180d23786b5ef62674f30838a56e46409bb38e26dc31fe9324356a7fa2125
import io
import json
import socket
import urllib.error
import urllib.request

import pytest

import llm_endpoint


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


HTTP_PROVIDERS = ["anthropic", "openai", "openai-compatible", "gemini", "ollama"]

KEY_ENVS = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "openai-compatible": "TEST_COMPAT_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "ollama": None,
}

ALL_KEY_ENVS = ["ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY", "TEST_COMPAT_API_KEY"]


class _UnreadableReply:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self, *args, **kwargs):
        return b"\x00\xff this is not a readable reply <<<"


def _http_error(code, body=b"{}"):
    return urllib.error.HTTPError(
        "http://example.invalid/", code, "error", {}, io.BytesIO(body)
    )


def _make_outcome(kind):
    if kind == "401":
        return ("raise", lambda: _http_error(401))
    if kind == "403":
        return ("raise", lambda: _http_error(403))
    if kind == "429":
        return ("raise", lambda: _http_error(429))
    if kind == "408":
        return ("raise", lambda: _http_error(408))
    if kind == "504":
        return ("raise", lambda: _http_error(504))
    if kind == "500":
        return ("raise", lambda: _http_error(500))
    if kind == "socket_timeout":
        return ("raise", lambda: socket.timeout("timed out"))
    if kind == "refused":
        return ("raise", lambda: urllib.error.URLError(ConnectionRefusedError(61, "Connection refused")))
    if kind == "unreadable":
        return ("return", lambda: _UnreadableReply())
    raise AssertionError(kind)


CASES = [
    ("401", "auth"),
    ("403", "auth"),
    ("429", "rate_limit"),
    ("408", "timeout"),
    ("504", "timeout"),
    ("500", "network"),
    ("socket_timeout", "timeout"),
    ("refused", "network"),
    ("unreadable", "network"),
]


def _write_config(tmp_path, monkeypatch, provider, model):
    lines = ["[llm]", "provider = " + json.dumps(provider), "model = " + json.dumps(model)]
    if provider == "openai-compatible":
        lines.append("base_url = " + json.dumps("http://127.0.0.1:9/v1"))
        lines.append("api_key_env = " + json.dumps("TEST_COMPAT_API_KEY"))
    path = tmp_path / "hotdocs.toml"
    path.write_text("\n".join(lines) + "\n")
    monkeypatch.setenv("VAR_HOTDOCS_CONFIG", str(path))
    return path


def _install_recorder(monkeypatch, outcome):
    calls = []
    action, make = outcome

    def recorder(request, *args, **kwargs):
        calls.append(request)
        if len(calls) > 1:
            raise AssertionError("urlopen called more than once")
        if action == "raise":
            raise make()
        return make()

    monkeypatch.setattr(urllib.request, "urlopen", recorder)
    return calls


@pytest.fixture
def workdir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    for name in ALL_KEY_ENVS:
        monkeypatch.delenv(name, raising=False)
    return tmp_path


@pytest.mark.parametrize("provider", HTTP_PROVIDERS)
@pytest.mark.parametrize("kind,expected", CASES)
def test_http_failure_classified_once_without_raising(workdir, monkeypatch, provider, kind, expected):
    model_name = "test-model"
    _write_config(workdir, monkeypatch, provider, model_name)
    key_env = KEY_ENVS[provider]
    if key_env:
        monkeypatch.setenv(key_env, "sk-test-not-a-real-key-123")
    calls = _install_recorder(monkeypatch, _make_outcome(kind))

    response = llm_endpoint.complete("Say hello.", provider + ":" + model_name)

    error = field(response, "model_call_error")
    assert error is not None
    assert field(error, "category") == expected
    assert field(response, "text") is None
    assert len(calls) == 1


@pytest.mark.parametrize("provider", ["anthropic", "openai", "gemini"])
def test_missing_key_reports_auth_without_call(workdir, monkeypatch, provider):
    model_name = "test-model"
    _write_config(workdir, monkeypatch, provider, model_name)
    calls = _install_recorder(monkeypatch, _make_outcome("500"))

    response = llm_endpoint.complete("Say hello.", provider + ":" + model_name)

    error = field(response, "model_call_error")
    assert error is not None
    assert field(error, "category") == "auth"
    assert field(response, "text") is None
    assert len(calls) == 0


def test_gemini_400_invalid_api_key_is_auth(workdir, monkeypatch):
    model_name = "test-model"
    _write_config(workdir, monkeypatch, "gemini", model_name)
    monkeypatch.setenv("GEMINI_API_KEY", "sk-test-not-a-real-key-123")
    body = json.dumps(
        {
            "error": {
                "code": 400,
                "message": "API key not valid. Please pass a valid API key.",
                "status": "INVALID_ARGUMENT",
                "details": [
                    {
                        "reason": "API_KEY_INVALID",
                        "description": "The API key is not valid.",
                    }
                ],
            }
        }
    ).encode("utf-8")
    calls = _install_recorder(monkeypatch, ("raise", lambda: _http_error(400, body)))

    response = llm_endpoint.complete("Say hello.", "gemini:" + model_name)

    error = field(response, "model_call_error")
    assert error is not None
    assert field(error, "category") == "auth"
    assert field(response, "text") is None
    assert len(calls) == 1