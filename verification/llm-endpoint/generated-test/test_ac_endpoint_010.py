# hotdocs-criterion: sha256:270fc0206695d747e153f207998cd123f36d8755593ee7f0da43ff1b9cdf3f80
import email.message
import io
import json
import os
import socket
import stat
import urllib.error
import urllib.request

import pytest

import llm_endpoint


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _url_of(request):
    if isinstance(request, str):
        return request
    return getattr(request, "full_url", None) or request.get_full_url()


def _timeout_of(args, kwargs):
    if "timeout" in kwargs:
        return kwargs["timeout"]
    if len(args) >= 2:
        return args[1]
    return None


class _FakeReply:
    def __init__(self, body):
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self, *args, **kwargs):
        return self._body


def _make_claude_dir(tmp_path):
    d = tmp_path / "with_claude"
    d.mkdir()
    script = d / "claude"
    script.write_text("#!/bin/sh\nexit 0\n")
    script.chmod(script.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return d


def _by_provider(entries):
    out = {}
    for e in entries:
        out[field(e, "provider")] = e
    return out


def test_detect_providers_entries_and_availability(tmp_path, monkeypatch):
    calls = []

    def failing_urlopen(*args, **kwargs):
        calls.append((_url_of(args[0]), _timeout_of(args, kwargs)))
        raise urllib.error.URLError(ConnectionRefusedError("refused"))

    monkeypatch.setattr(urllib.request, "urlopen", failing_urlopen)

    empty_dir = tmp_path / "no_claude"
    empty_dir.mkdir()
    env = {"PATH": str(empty_dir), "OPENAI_API_KEY": "k", "GEMINI_API_KEY": " "}

    entries = llm_endpoint.detect_providers(env=env)
    assert isinstance(entries, list)

    provider_names = list(llm_endpoint.PROVIDERS.keys())
    got_names = [field(e, "provider") for e in entries]
    assert sorted(got_names) == sorted(provider_names)
    assert len(got_names) == len(set(got_names))

    for e in entries:
        for key in ("provider", "available", "reason", "suggested_model", "api_key_env"):
            field(e, key)  # must exist
        assert isinstance(field(e, "available"), bool)

    by = _by_provider(entries)
    available = sorted(name for name, e in by.items() if field(e, "available"))
    assert available == ["openai"]

    # With a claude executable on PATH, claude-cli is available too.
    claude_dir = _make_claude_dir(tmp_path)
    env2 = dict(env)
    env2["PATH"] = str(claude_dir) + os.pathsep + str(empty_dir)
    entries2 = llm_endpoint.detect_providers(env=env2)
    by2 = _by_provider(entries2)
    assert sorted(by2.keys()) == sorted(provider_names)
    available2 = sorted(name for name, e in by2.items() if field(e, "available"))
    assert available2 == ["claude-cli", "openai"]


def test_detect_providers_ollama_answering(tmp_path, monkeypatch):
    calls = []

    def answering_urlopen(*args, **kwargs):
        calls.append((_url_of(args[0]), _timeout_of(args, kwargs)))
        return _FakeReply(b'{"models": []}')

    monkeypatch.setattr(urllib.request, "urlopen", answering_urlopen)

    empty_dir = tmp_path / "no_claude"
    empty_dir.mkdir()
    env = {"PATH": str(empty_dir)}

    entries = llm_endpoint.detect_providers(env=env)
    by = _by_provider(entries)
    assert "ollama" in by
    assert field(by["ollama"], "available") is True

    probe_calls = [c for c in calls if c[0] and "/api/tags" in c[0]]
    assert probe_calls, "Ollama probe did not request /api/tags"
    for _, timeout in probe_calls:
        assert timeout is not None
        assert 0 < float(timeout) <= 1.5


def test_check_connection_ok_then_auth_failure(tmp_path, monkeypatch):
    secret = "sk-test-secret-value-1234567890"
    monkeypatch.setenv("OPENAI_API_KEY", secret)
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    monkeypatch.chdir(tmp_path)

    reply_body = json.dumps(
        {
            "id": "x",
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

    def ok_urlopen(*args, **kwargs):
        return _FakeReply(reply_body)

    monkeypatch.setattr(urllib.request, "urlopen", ok_urlopen)
    result_ok = llm_endpoint.check_connection("openai", "m")
    assert field(result_ok, "ok") is True
    assert field(result_ok, "error") is None

    def unauthorized_urlopen(*args, **kwargs):
        url = _url_of(args[0])
        hdrs = email.message.Message()
        raise urllib.error.HTTPError(
            url,
            401,
            "Unauthorized",
            hdrs,
            io.BytesIO(b'{"error": {"message": "Incorrect API key provided"}}'),
        )

    monkeypatch.setattr(urllib.request, "urlopen", unauthorized_urlopen)
    result_bad = llm_endpoint.check_connection("openai", "m")
    assert field(result_bad, "ok") is False
    error = field(result_bad, "error")
    assert error is not None
    assert field(error, "category") == "auth"
    message = field(error, "message")
    assert isinstance(message, str)
    assert secret not in message

    calls_dir = tmp_path / ".hotdocs" / "calls"
    assert not calls_dir.exists() or not any(calls_dir.iterdir())

    with pytest.raises(ValueError):
        llm_endpoint.check_connection("no-such-provider", "m")