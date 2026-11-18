# hotdocs-criterion: sha256:0144371462bc34f251f30e9cd799cb491277de442a9e0a619c737e047b34aa36
import io
import json
import os
import stat
import urllib.error
import urllib.request
import email.message

import pytest

import llm_endpoint


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def has_field(value, name):
    if isinstance(value, dict):
        return name in value
    return hasattr(value, name)


class _FakeReply:
    def __init__(self, body: bytes):
        self._body = body

    def read(self, *args, **kwargs):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def _raising_urlopen(*args, **kwargs):
    raise urllib.error.URLError("connection refused")


def _entries_by_name(entries):
    entries = list(entries)
    by_name = {}
    for entry in entries:
        by_name[field(entry, "provider")] = entry
    return entries, by_name


def _make_claude_dir(base):
    d = base / "with_claude"
    d.mkdir()
    exe = d / "claude"
    exe.write_text("#!/bin/sh\nexit 0\n")
    exe.chmod(exe.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return d


def test_detect_providers_only_openai_available_then_claude_cli_with_claude_on_path(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(urllib.request, "urlopen", _raising_urlopen)

    empty_dir = tmp_path / "no_claude"
    empty_dir.mkdir()

    env = {
        "PATH": str(empty_dir),
        "OPENAI_API_KEY": "k",
        "GEMINI_API_KEY": " ",
    }
    entries = llm_endpoint.detect_providers(env=env)
    entries, by_name = _entries_by_name(entries)

    provider_names = set(llm_endpoint.PROVIDERS)
    assert len(entries) == len(provider_names)
    assert set(by_name) == provider_names

    for name, entry in by_name.items():
        for key in ("provider", "available", "reason", "suggested_model", "api_key_env"):
            assert has_field(entry, key), f"{name} entry lacks {key}"
        assert field(entry, "suggested_model") == field(
            llm_endpoint.PROVIDERS[name], "suggested_model"
        )

    available = {name for name, entry in by_name.items() if bool(field(entry, "available"))}
    assert available == {"openai"}

    claude_dir = _make_claude_dir(tmp_path)
    env_with_claude = dict(env)
    env_with_claude["PATH"] = str(claude_dir)
    entries2 = llm_endpoint.detect_providers(env=env_with_claude)
    entries2, by_name2 = _entries_by_name(entries2)

    assert set(by_name2) == provider_names
    assert len(entries2) == len(provider_names)
    available2 = {
        name for name, entry in by_name2.items() if bool(field(entry, "available"))
    }
    assert available2 == {"openai", "claude-cli"}


def test_detect_providers_ollama_available_when_probe_answers_within_a_second(
    tmp_path, monkeypatch
):
    calls = []

    def answering_urlopen(request, *args, **kwargs):
        if "timeout" in kwargs:
            timeout = kwargs["timeout"]
        elif args:
            timeout = args[-1] if not isinstance(args[0], (bytes, type(None))) else (
                args[1] if len(args) > 1 else None
            )
        else:
            timeout = None
        url = getattr(request, "full_url", request)
        calls.append({"url": str(url), "timeout": timeout})
        return _FakeReply(json.dumps({"models": []}).encode("utf-8"))

    monkeypatch.setattr(urllib.request, "urlopen", answering_urlopen)

    empty_dir = tmp_path / "no_claude"
    empty_dir.mkdir()
    entries = llm_endpoint.detect_providers(env={"PATH": str(empty_dir)})
    entries, by_name = _entries_by_name(entries)

    assert "ollama" in by_name
    assert bool(field(by_name["ollama"], "available")) is True

    assert calls, "the Ollama probe never called urllib.request.urlopen"
    for call in calls:
        timeout = call["timeout"]
        assert timeout is not None, "the Ollama probe set no timeout"
        assert 0 < float(timeout) <= 1.5


def test_check_connection_ok_then_auth_error_no_call_log_and_unknown_provider(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    secret = "sk-test-secret-value-1234567890"
    monkeypatch.setenv("OPENAI_API_KEY", secret)

    body = {
        "id": "chatcmpl-1",
        "object": "chat.completion",
        "model": "m",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": "OK"},
                "finish_reason": "stop",
            }
        ],
        "output_text": "OK",
        "output": [
            {
                "type": "message",
                "role": "assistant",
                "content": [{"type": "output_text", "text": "OK"}],
            }
        ],
    }

    def ok_urlopen(request, *args, **kwargs):
        return _FakeReply(json.dumps(body).encode("utf-8"))

    monkeypatch.setattr(urllib.request, "urlopen", ok_urlopen)
    result_ok = llm_endpoint.check_connection("openai", "m")
    assert field(result_ok, "ok") is True
    assert field(result_ok, "error") is None

    def unauthorized_urlopen(request, *args, **kwargs):
        url = getattr(request, "full_url", str(request))
        raise urllib.error.HTTPError(
            url,
            401,
            "Unauthorized",
            email.message.Message(),
            io.BytesIO(b'{"error": {"message": "Incorrect API key provided"}}'),
        )

    monkeypatch.setattr(urllib.request, "urlopen", unauthorized_urlopen)
    result_fail = llm_endpoint.check_connection("openai", "m")
    assert field(result_fail, "ok") is False
    error = field(result_fail, "error")
    assert error is not None
    assert field(error, "category") == "auth"
    assert has_field(error, "message")
    assert secret not in str(field(error, "message"))
    assert secret not in repr(result_fail)

    calls_dir = tmp_path / ".hotdocs" / "calls"
    if calls_dir.exists():
        assert list(calls_dir.iterdir()) == []

    with pytest.raises(ValueError):
        llm_endpoint.check_connection("no-such-provider", "m")