import io
import json
import os
import stat
import urllib.error
import urllib.request
from email.message import Message

import pytest

import llm_endpoint


REQUIRED_ENTRY_KEYS = ("provider", "available", "reason", "suggested_model", "api_key_env")


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def has_field(value, name):
    if isinstance(value, dict):
        return name in value
    return hasattr(value, name)


class FakeReply:
    def __init__(self, body: bytes):
        self._body = body
        self.status = 200
        self.code = 200
        self.headers = Message()

    def read(self, *args, **kwargs):
        return self._body

    def getcode(self):
        return 200

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def _url_of(request):
    if isinstance(request, str):
        return request
    return getattr(request, "full_url", None) or getattr(request, "get_full_url", lambda: "")()


def _timeout_of(args, kwargs):
    if "timeout" in kwargs:
        return kwargs["timeout"]
    if len(args) >= 3:
        return args[2]
    return None


def _make_empty_dir(tmp_path, name):
    d = tmp_path / name
    d.mkdir()
    return d


def _make_claude_dir(tmp_path):
    d = tmp_path / "with_claude"
    d.mkdir()
    exe = d / "claude"
    exe.write_text("#!/bin/sh\nexit 0\n")
    exe.chmod(exe.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return d


def _available_names(entries):
    return {field(e, "provider") for e in entries if field(e, "available")}


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.chdir(work)
    return work


def test_detect_providers_shape_and_availability_without_ollama(tmp_path, monkeypatch):
    calls = []

    def raising_urlopen(request, *args, **kwargs):
        calls.append((_url_of(request), _timeout_of((request,) + args, kwargs)))
        raise urllib.error.URLError(ConnectionRefusedError("connection refused"))

    monkeypatch.setattr(urllib.request, "urlopen", raising_urlopen)

    no_claude = _make_empty_dir(tmp_path, "no_claude")
    env = {"PATH": str(no_claude), "OPENAI_API_KEY": "k", "GEMINI_API_KEY": " "}

    entries = list(llm_endpoint.detect_providers(env=env))

    provider_names = [field(e, "provider") for e in entries]
    assert len(entries) == len(llm_endpoint.PROVIDERS)
    assert set(provider_names) == set(llm_endpoint.PROVIDERS.keys())
    assert len(set(provider_names)) == len(provider_names)

    for e in entries:
        for key in REQUIRED_ENTRY_KEYS:
            assert has_field(e, key), f"entry {e!r} lacks {key}"

    assert _available_names(entries) == {"openai"}

    # With a claude executable on PATH, claude-cli becomes available too.
    with_claude = _make_claude_dir(tmp_path)
    env2 = {"PATH": str(with_claude), "OPENAI_API_KEY": "k", "GEMINI_API_KEY": " "}
    entries2 = list(llm_endpoint.detect_providers(env=env2))
    assert len(entries2) == len(llm_endpoint.PROVIDERS)
    assert set(field(e, "provider") for e in entries2) == set(llm_endpoint.PROVIDERS.keys())
    assert _available_names(entries2) == {"openai", "claude-cli"}


def test_detect_providers_ollama_answering_with_short_timeout(tmp_path, monkeypatch):
    calls = []

    def answering_urlopen(request, *args, **kwargs):
        calls.append((_url_of(request), _timeout_of((request,) + args, kwargs)))
        return FakeReply(json.dumps({"models": []}).encode("utf-8"))

    monkeypatch.setattr(urllib.request, "urlopen", answering_urlopen)

    no_claude = _make_empty_dir(tmp_path, "no_claude_2")
    env = {"PATH": str(no_claude)}

    entries = list(llm_endpoint.detect_providers(env=env))

    by_name = {field(e, "provider"): e for e in entries}
    assert "ollama" in by_name
    assert field(by_name["ollama"], "available")

    assert calls, "the Ollama probe never called urllib.request.urlopen"
    probe_calls = [c for c in calls if c[0] and "/api/tags" in c[0]]
    relevant = probe_calls or calls
    for _url, timeout in relevant:
        assert timeout is not None, "Ollama probe must pass a timeout"
        assert 0 < float(timeout) <= 1.5, f"Ollama probe timeout too long: {timeout}"


def _openai_reply_body():
    return json.dumps(
        {
            "id": "chatcmpl-1",
            "object": "chat.completion",
            "model": "m",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "ok"},
                    "finish_reason": "stop",
                }
            ],
            "output_text": "ok",
            "output": [
                {
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": "ok"}],
                }
            ],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        }
    ).encode("utf-8")


def _calls_dir_records(work):
    calls_dir = work / ".hotdocs" / "calls"
    if not calls_dir.exists():
        return []
    return [p for p in calls_dir.rglob("*") if p.is_file()]


def test_check_connection_ok_then_auth_error_no_log_and_unknown_provider(_isolate, monkeypatch):
    work = _isolate
    secret = "sk-test-secret-value-1234567890"
    monkeypatch.setenv("OPENAI_API_KEY", secret)

    def ok_urlopen(request, *args, **kwargs):
        return FakeReply(_openai_reply_body())

    monkeypatch.setattr(urllib.request, "urlopen", ok_urlopen)
    result_ok = llm_endpoint.check_connection("openai", "m")

    assert field(result_ok, "ok") is True
    assert field(result_ok, "error") is None

    def unauthorized_urlopen(request, *args, **kwargs):
        url = _url_of(request) or "https://api.openai.com/v1/chat/completions"
        raise urllib.error.HTTPError(
            url,
            401,
            "Unauthorized",
            Message(),
            io.BytesIO(b'{"error": {"message": "Incorrect API key provided", "type": "invalid_request_error"}}'),
        )

    monkeypatch.setattr(urllib.request, "urlopen", unauthorized_urlopen)
    result_bad = llm_endpoint.check_connection("openai", "m")

    assert field(result_bad, "ok") is False
    error = field(result_bad, "error")
    assert error is not None
    assert field(error, "category") == "auth"
    assert has_field(error, "message")
    assert secret not in repr(result_bad)
    assert secret not in str(field(error, "message"))

    assert _calls_dir_records(work) == [], "check_connection must not write a call-log record"

    with pytest.raises(ValueError):
        llm_endpoint.check_connection("no-such-provider", "m")