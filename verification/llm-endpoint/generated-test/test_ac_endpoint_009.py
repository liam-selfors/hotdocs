import io
import json
import socket
import urllib.error
import urllib.request
import email.message

import pytest

import llm_endpoint


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


KEY_ENVS = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "gemini": "GEMINI_API_KEY",
}

MODELS = {
    "anthropic": "anthropic:claude-sonnet-5",
    "openai": "openai:gpt-6-astra",
    "openai-compatible": "openai-compatible:test-model",
    "gemini": "gemini:gemini-4-argon",
    "ollama": "ollama:llama3.2",
}

HTTP_PROVIDERS = ["anthropic", "openai", "openai-compatible", "gemini", "ollama"]


def _http_error(code, body=b'{"error": {"message": "boom"}}'):
    hdrs = email.message.Message()
    hdrs["Content-Type"] = "application/json"
    return urllib.error.HTTPError(
        "http://example.invalid/", code, "error", hdrs, io.BytesIO(body)
    )


class _GarbageReply:
    def __init__(self):
        self.status = 200
        self.code = 200

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self, *args, **kwargs):
        return b"\xff\xfe<<< this is not a readable reply body >>>\x00"

    def getcode(self):
        return 200

    def close(self):
        pass


def _make_outcome(kind):
    """Return a callable that, when invoked, raises or returns per `kind`."""
    if isinstance(kind, int):
        def act():
            raise _http_error(kind)
    elif kind == "socket_timeout":
        def act():
            raise socket.timeout("timed out")
    elif kind == "refused":
        def act():
            raise urllib.error.URLError(
                ConnectionRefusedError(61, "Connection refused")
            )
    elif kind == "unreadable":
        def act():
            return _GarbageReply()
    else:  # pragma: no cover
        raise AssertionError(kind)
    return act


FAILURES = [
    (401, "auth"),
    (403, "auth"),
    (429, "rate_limit"),
    (408, "timeout"),
    (504, "timeout"),
    (500, "network"),
    ("socket_timeout", "timeout"),
    ("refused", "network"),
    ("unreadable", "network"),
]


def _install_recorder(monkeypatch, log_path, act):
    def recorder(*args, **kwargs):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"called": True}) + "\n")
        return act()

    monkeypatch.setattr(urllib.request, "urlopen", recorder)


def _calls(log_path):
    if not log_path.exists():
        return 0
    return len([l for l in log_path.read_text(encoding="utf-8").splitlines() if l.strip()])


def _prepare_workdir(tmp_path, monkeypatch, provider):
    workdir = tmp_path / "work"
    workdir.mkdir()
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    monkeypatch.chdir(workdir)
    if provider == "openai-compatible":
        llm_endpoint.save_config(
            workdir / "hotdocs.toml",
            "openai-compatible",
            "test-model",
            base_url="http://127.0.0.1:9/v1",
        )
    return workdir


def _assert_failed(resp, expected_category):
    err = field(resp, "model_call_error")
    assert err is not None, f"expected a model_call_error, got {resp!r}"
    assert field(err, "category") == expected_category, (
        f"expected {expected_category}, got {field(err, 'category')!r}"
    )
    assert field(resp, "text") is None


@pytest.mark.parametrize("provider", HTTP_PROVIDERS)
@pytest.mark.parametrize(
    "kind,expected", FAILURES, ids=[str(k) for k, _ in FAILURES]
)
def test_http_failure_classified_once_no_raise(tmp_path, monkeypatch, provider, kind, expected):
    for p, env in KEY_ENVS.items():
        monkeypatch.setenv(env, "test-fake-key-value-0000")
    _prepare_workdir(tmp_path, monkeypatch, provider)

    log_path = tmp_path / "urlopen_calls.log"
    _install_recorder(monkeypatch, log_path, _make_outcome(kind))

    try:
        resp = llm_endpoint.complete("Say hello.", MODELS[provider])
    except Exception as exc:  # nothing may be raised
        pytest.fail(f"complete() raised {type(exc).__name__}: {exc}")

    _assert_failed(resp, expected)
    assert _calls(log_path) == 1, "urlopen recorder must be called exactly once"


@pytest.mark.parametrize("provider", sorted(KEY_ENVS))
def test_missing_key_reports_auth_without_call(tmp_path, monkeypatch, provider):
    for env in KEY_ENVS.values():
        monkeypatch.delenv(env, raising=False)
    _prepare_workdir(tmp_path, monkeypatch, provider)

    log_path = tmp_path / "urlopen_calls.log"

    def act():
        raise AssertionError("urlopen must not be called")

    _install_recorder(monkeypatch, log_path, act)

    try:
        resp = llm_endpoint.complete("Say hello.", MODELS[provider])
    except Exception as exc:
        pytest.fail(f"complete() raised {type(exc).__name__}: {exc}")

    _assert_failed(resp, "auth")
    assert _calls(log_path) == 0, "recorder must never be called without a key"


def test_gemini_400_invalid_api_key_is_auth(tmp_path, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-fake-key-value-0000")
    _prepare_workdir(tmp_path, monkeypatch, "gemini")

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

    log_path = tmp_path / "urlopen_calls.log"

    def act():
        raise _http_error(400, body)

    _install_recorder(monkeypatch, log_path, act)

    try:
        resp = llm_endpoint.complete("Say hello.", MODELS["gemini"])
    except Exception as exc:
        pytest.fail(f"complete() raised {type(exc).__name__}: {exc}")

    _assert_failed(resp, "auth")
    assert _calls(log_path) == 1