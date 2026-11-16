"""AC-ENDPOINT-009 (Covers: R-ENDPOINT-004).

Every HTTP provider classifies each failure into exactly one category,
makes exactly one call, and never raises; a provider needing a key with
none in the environment reports `auth` without a call; Gemini's
"API key not valid" 400 maps to `auth`.
"""

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


KEY_VARS = ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY")


# provider -> model string passed to complete() (openai-compatible is configured
# through hotdocs.toml in the current directory and called by bare name).
HTTP_PROVIDERS = {
    "anthropic": "anthropic:claude-sonnet-5",
    "openai": "openai:gpt-6-astra",
    "openai-compatible": "compat-model",
    "gemini": "gemini:gemini-4-argon",
    "ollama": "ollama:llama3.2",
}

KEYED_PROVIDERS = {
    "anthropic": ("anthropic:claude-sonnet-5", "ANTHROPIC_API_KEY"),
    "openai": ("openai:gpt-6-astra", "OPENAI_API_KEY"),
    "gemini": ("gemini:gemini-4-argon", "GEMINI_API_KEY"),
}


def _http_error(code, body=b"{}"):
    return urllib.error.HTTPError(
        "http://example.invalid/", code, "error", email.message.Message(), io.BytesIO(body)
    )


class _UnreadableReply:
    status = 200
    code = 200

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self, *args, **kwargs):
        return b"\x00\xff<<this is not a readable reply body>>"

    def getcode(self):
        return 200

    def close(self):
        pass


def _raise(exc):
    def outcome():
        raise exc

    return outcome


OUTCOMES = [
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
    ("unreadable_body", lambda: (lambda: _UnreadableReply()), "network"),
]


def _make_recorder(outcome):
    calls = []

    def recorder(request, *args, **kwargs):
        calls.append((request, args, kwargs))
        return outcome()

    return recorder, calls


def _prepare_env(monkeypatch, tmp_path, provider, with_keys=True):
    workdir = tmp_path / "work"
    workdir.mkdir()
    monkeypatch.chdir(workdir)
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    for var in KEY_VARS:
        monkeypatch.delenv(var, raising=False)
    if with_keys:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-anthropic-key-not-real")
        monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key-not-real")
        monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key-not-real")
    if provider == "openai-compatible":
        (workdir / "hotdocs.toml").write_text(
            "[llm]\n"
            'provider = "openai-compatible"\n'
            'model = "compat-model"\n'
            'base_url = "http://127.0.0.1:9/v1"\n',
            encoding="utf-8",
        )
    return workdir


@pytest.mark.parametrize("provider", sorted(HTTP_PROVIDERS))
@pytest.mark.parametrize(
    "outcome_name,outcome_factory,expected",
    OUTCOMES,
    ids=[o[0] for o in OUTCOMES],
)
def test_http_failure_is_classified_once_without_raising(
    monkeypatch, tmp_path, provider, outcome_name, outcome_factory, expected
):
    _prepare_env(monkeypatch, tmp_path, provider)
    recorder, calls = _make_recorder(outcome_factory())
    monkeypatch.setattr(urllib.request, "urlopen", recorder)

    try:
        result = llm_endpoint.complete("Say hello.", HTTP_PROVIDERS[provider])
    except Exception as exc:  # pragma: no cover - the assertion is the point
        pytest.fail(f"complete() raised {type(exc).__name__} for {provider}/{outcome_name}")

    error = field(result, "model_call_error")
    assert error is not None, f"{provider}/{outcome_name}: expected a model_call_error"
    assert field(error, "category") == expected, (
        f"{provider}/{outcome_name}: category {field(error, 'category')!r}, "
        f"expected {expected!r}"
    )
    assert field(result, "text") is None
    assert len(calls) == 1, f"{provider}/{outcome_name}: urlopen called {len(calls)} times"


@pytest.mark.parametrize("provider", sorted(KEYED_PROVIDERS))
def test_missing_key_reports_auth_without_call(monkeypatch, tmp_path, provider):
    _prepare_env(monkeypatch, tmp_path, provider, with_keys=False)
    model, _key_var = KEYED_PROVIDERS[provider]

    def unexpected():
        raise AssertionError("urlopen must not be reached")

    recorder, calls = _make_recorder(unexpected)
    monkeypatch.setattr(urllib.request, "urlopen", recorder)

    try:
        result = llm_endpoint.complete("Say hello.", model)
    except Exception as exc:  # pragma: no cover
        pytest.fail(f"complete() raised {type(exc).__name__} for {provider} with no key")

    error = field(result, "model_call_error")
    assert error is not None
    assert field(error, "category") == "auth"
    assert field(result, "text") is None
    assert calls == [], f"{provider}: urlopen was called {len(calls)} times without a key"


def test_gemini_invalid_api_key_400_is_auth(monkeypatch, tmp_path):
    _prepare_env(monkeypatch, tmp_path, "gemini")
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

    def outcome():
        raise _http_error(400, body)

    recorder, calls = _make_recorder(outcome)
    monkeypatch.setattr(urllib.request, "urlopen", recorder)

    try:
        result = llm_endpoint.complete("Say hello.", "gemini:gemini-4-argon")
    except Exception as exc:  # pragma: no cover
        pytest.fail(f"complete() raised {type(exc).__name__}")

    error = field(result, "model_call_error")
    assert error is not None
    assert field(error, "category") == "auth"
    assert field(result, "text") is None
    assert len(calls) == 1