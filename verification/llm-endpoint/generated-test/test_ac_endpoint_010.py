# hotdocs-criterion: sha256:9ce4663fe9fab59fc8515a7abf5c33297ded40219bb963580851075b75ba6b49
import email.message
import io
import json
import os
import stat
import urllib.error
import urllib.request

import pytest

import llm_endpoint


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


ENTRY_KEYS = ("provider", "available", "reason", "suggested_model", "api_key_env")


class FakeReply:
    def __init__(self, body):
        self._body = body
        self.status = 200

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self, *args, **kwargs):
        return self._body

    def getcode(self):
        return 200


def _raising_urlopen(*args, **kwargs):
    raise urllib.error.URLError(ConnectionRefusedError("connection refused"))


def _entries_by_name(entries):
    by_name = {}
    for entry in entries:
        by_name[field(entry, "provider")] = entry
    return by_name


def _check_shape(entries):
    names = [field(e, "provider") for e in entries]
    assert sorted(names) == sorted(llm_endpoint.PROVIDERS.keys())
    assert len(names) == len(set(names))
    for entry in entries:
        for key in ENTRY_KEYS:
            if isinstance(entry, dict):
                assert key in entry, (key, entry)
            else:
                assert hasattr(entry, key), (key, entry)


def _write_claude(directory):
    path = directory / "claude"
    path.write_text("#!/bin/sh\nexit 0\n")
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return path


def test_detect_providers_entries_and_availability(tmp_path, monkeypatch):
    # The process environment holds a key that must NOT be consulted.
    monkeypatch.setenv("ANTHROPIC_API_KEY", "process-only-key")
    monkeypatch.setattr(urllib.request, "urlopen", _raising_urlopen)

    empty_dir = tmp_path / "empty_bin"
    empty_dir.mkdir()
    env = {"PATH": str(empty_dir), "OPENAI_API_KEY": "k", "GEMINI_API_KEY": " "}

    entries = llm_endpoint.detect_providers(env=env)
    _check_shape(entries)
    available = sorted(
        field(e, "provider") for e in entries if field(e, "available") is True
    )
    assert available == ["openai"]
    for e in entries:
        assert isinstance(field(e, "available"), bool)

    claude_dir = tmp_path / "claude_bin"
    claude_dir.mkdir()
    _write_claude(claude_dir)
    env2 = dict(env)
    env2["PATH"] = str(claude_dir)

    entries2 = llm_endpoint.detect_providers(env=env2)
    _check_shape(entries2)
    available2 = sorted(
        field(e, "provider") for e in entries2 if field(e, "available") is True
    )
    assert available2 == ["claude-cli", "openai"]


def test_detect_providers_ollama_answering(tmp_path, monkeypatch):
    timeouts = []

    def answering_urlopen(*args, **kwargs):
        if "timeout" in kwargs:
            timeouts.append(kwargs["timeout"])
        elif len(args) >= 3:
            timeouts.append(args[2])
        else:
            timeouts.append(None)
        return FakeReply(json.dumps({"models": []}).encode("utf-8"))

    monkeypatch.setattr(urllib.request, "urlopen", answering_urlopen)

    empty_dir = tmp_path / "empty_bin"
    empty_dir.mkdir()
    env = {"PATH": str(empty_dir)}

    entries = llm_endpoint.detect_providers(env=env)
    _check_shape(entries)
    by_name = _entries_by_name(entries)
    assert field(by_name["ollama"], "available") is True

    assert timeouts, "the Ollama probe never called urlopen"
    for t in timeouts:
        assert t is not None
        assert 0 < float(t) <= 1.5


def test_check_connection_ok_then_auth_no_log(tmp_path, monkeypatch):
    secret = "sk-test-secret-value-123456"
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", secret)
    workdir = tmp_path / "work"
    workdir.mkdir()
    monkeypatch.chdir(workdir)

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
        }
    ).encode("utf-8")

    def ok_urlopen(*args, **kwargs):
        return FakeReply(reply_body)

    monkeypatch.setattr(urllib.request, "urlopen", ok_urlopen)
    result_ok = llm_endpoint.check_connection("openai", "m")
    assert field(result_ok, "ok") is True
    assert field(result_ok, "error") is None

    def auth_urlopen(*args, **kwargs):
        hdrs = email.message.Message()
        raise urllib.error.HTTPError(
            "https://api.openai.com/v1/chat/completions",
            401,
            "Unauthorized",
            hdrs,
            io.BytesIO(b'{"error": {"message": "Incorrect API key provided"}}'),
        )

    monkeypatch.setattr(urllib.request, "urlopen", auth_urlopen)
    result_fail = llm_endpoint.check_connection("openai", "m")
    assert field(result_fail, "ok") is False
    error = field(result_fail, "error")
    assert error is not None
    assert field(error, "category") == "auth"
    message = field(error, "message")
    assert isinstance(message, str)
    assert secret not in message

    calls_dir = workdir / ".hotdocs" / "calls"
    if calls_dir.exists():
        assert list(calls_dir.iterdir()) == []

    with pytest.raises(ValueError):
        llm_endpoint.check_connection("no-such-provider", "m")