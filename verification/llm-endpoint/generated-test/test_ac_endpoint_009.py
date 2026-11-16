import io
import socket
import urllib.error
import urllib.request

import pytest

import llm_endpoint


HTTP_PROVIDER_MODELS = [
    ("anthropic", "anthropic:claude-sonnet-5"),
    ("openai", "openai:gpt-6-astra"),
    ("openai-compatible", "openai-compatible:local-model"),
    ("gemini", "gemini:gemini-4-argon"),
    ("ollama", "ollama:llama3.2"),
]

KEY_ENVS = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "gemini": "GEMINI_API_KEY",
}

VALID_CATEGORIES = {"network", "auth", "rate_limit", "timeout"}


def _field(value, name):
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def _http_error(code, body=b'{"error": {"message": "vendor says something specific"}}'):
    return urllib.error.HTTPError(
        "http://example.invalid/endpoint",
        code,
        "error",
        {},
        io.BytesIO(body),
    )


class _UnreadableResponse:
    status = 200
    code = 200
    headers = {}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self, *args, **kwargs):
        return b"\x00\xff\xfe this is { not json at all"

    def getcode(self):
        return 200

    def close(self):
        pass


def _raise(exc):
    def action():
        raise exc

    return action


FAILURE_CASES = [
    ("http_401", lambda: _raise(_http_error(401)), "auth"),
    ("http_403", lambda: _raise(_http_error(403)), "auth"),
    ("http_429", lambda: _raise(_http_error(429)), "rate_limit"),
    ("http_408", lambda: _raise(_http_error(408)), "timeout"),
    ("http_504", lambda: _raise(_http_error(504)), "timeout"),
    ("http_500", lambda: _raise(_http_error(500)), "network"),
    ("socket_timeout", lambda: _raise(socket.timeout("timed out")), "timeout"),
    (
        "connection_refused",
        lambda: _raise(
            urllib.error.URLError(ConnectionRefusedError(61, "Connection refused"))
        ),
        "network",
    ),
    ("unreadable_body", lambda: (lambda: _UnreadableResponse()), "network"),
]


def _install_recorder(monkeypatch, action):
    calls = []

    def fake_urlopen(request, *args, **kwargs):
        calls.append({"request": request, "args": args, "kwargs": kwargs})
        return action()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    return calls


def _prepare_env(monkeypatch, tmp_path, provider, with_keys=True):
    workdir = tmp_path / "work"
    workdir.mkdir()
    monkeypatch.chdir(workdir)
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    for env_name in KEY_ENVS.values():
        monkeypatch.delenv(env_name, raising=False)
    if with_keys:
        for env_name in KEY_ENVS.values():
            monkeypatch.setenv(env_name, "fake-test-key-not-real-0000")
    if provider == "openai-compatible":
        (workdir / "hotdocs.toml").write_text(
            "[llm]\n"
            'provider = "openai-compatible"\n'
            'model = "local-model"\n'
            'base_url = "http://127.0.0.1:9/v1"\n',
            encoding="utf-8",
        )
    return workdir


def _assert_failed_with(result, expected_category):
    error = _field(result, "model_call_error")
    assert error is not None, "expected a model_call_error, got %r" % (result,)
    assert _field(result, "text") is None
    category = _field(error, "category")
    assert category in VALID_CATEGORIES
    assert category == expected_category, (
        "expected category %r, got %r (result=%r)" % (expected_category, category, result)
    )


@pytest.mark.parametrize(
    "case_name,action_factory,expected_category",
    FAILURE_CASES,
    ids=[c[0] for c in FAILURE_CASES],
)
@pytest.mark.parametrize(
    "provider,model",
    HTTP_PROVIDER_MODELS,
    ids=[p[0] for p in HTTP_PROVIDER_MODELS],
)
def test_http_failure_classified_once_without_raising(
    monkeypatch, tmp_path, provider, model, case_name, action_factory, expected_category
):
    _prepare_env(monkeypatch, tmp_path, provider, with_keys=True)
    calls = _install_recorder(monkeypatch, action_factory())

    result = llm_endpoint.complete("Say hello.", model)

    _assert_failed_with(result, expected_category)
    assert len(calls) == 1, "recorder called %d times for %s/%s" % (
        len(calls),
        provider,
        case_name,
    )


@pytest.mark.parametrize(
    "provider,model",
    [
        ("anthropic", "anthropic:claude-sonnet-5"),
        ("openai", "openai:gpt-6-astra"),
        ("gemini", "gemini:gemini-4-argon"),
    ],
    ids=["anthropic", "openai", "gemini"],
)
def test_missing_key_reports_auth_without_calling(monkeypatch, tmp_path, provider, model):
    _prepare_env(monkeypatch, tmp_path, provider, with_keys=False)

    def should_not_be_called():
        raise AssertionError("urlopen must not be called without a key")

    calls = _install_recorder(monkeypatch, should_not_be_called)

    result = llm_endpoint.complete("Say hello.", model)

    _assert_failed_with(result, "auth")
    assert calls == []


def test_gemini_400_invalid_api_key_is_auth(monkeypatch, tmp_path):
    _prepare_env(monkeypatch, tmp_path, "gemini", with_keys=True)
    body = (
        b'{"error": {"code": 400, '
        b'"message": "API key not valid. Please pass a valid API key.", '
        b'"status": "INVALID_ARGUMENT", '
        b'"details": [{"@type": "type.googleapis.com/google.rpc.ErrorInfo", '
        b'"reason": "API_KEY_INVALID", "domain": "googleapis.com"}]}}'
    )
    calls = _install_recorder(monkeypatch, _raise(_http_error(400, body)))

    result = llm_endpoint.complete("Say hello.", "gemini:gemini-4-argon")

    _assert_failed_with(result, "auth")
    assert len(calls) == 1