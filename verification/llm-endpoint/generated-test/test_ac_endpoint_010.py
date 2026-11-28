# hotdocs-criterion: sha256:cc73ed34e4281a992a8e3c282c01ff6f83fb62b10b0cc016adc2d05b4022b94d
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


class FakeResponse:
    def __init__(self, body):
        self._body = body
        self.status = 200
        self.code = 200
        self.headers = {}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self, *args, **kwargs):
        return self._body

    def getcode(self):
        return 200

    def close(self):
        pass


def _raising_urlopen(*args, **kwargs):
    raise urllib.error.URLError("connection refused")


def _by_name(entries):
    out = {}
    for entry in entries:
        out[field(entry, "provider")] = entry
    return out


def _check_entries(entries):
    entries = list(entries)
    names = [field(e, "provider") for e in entries]
    assert sorted(names) == sorted(llm_endpoint.PROVIDERS.keys())
    assert len(names) == len(set(names))
    for entry in entries:
        for key in ENTRY_KEYS:
            field(entry, key)
        assert isinstance(field(entry, "available"), bool)
    return _by_name(entries)


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.chdir(work)
    return work


def test_detect_providers_keys_path_and_failed_probe(tmp_path, monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen", _raising_urlopen)
    empty_dir = tmp_path / "empty_bin"
    empty_dir.mkdir()
    env = {"PATH": str(empty_dir), "OPENAI_API_KEY": "k", "GEMINI_API_KEY": " "}

    entries = llm_endpoint.detect_providers(env=env)
    by_name = _check_entries(entries)
    available = sorted(n for n, e in by_name.items() if field(e, "available"))
    assert available == ["openai"]

    claude_dir = tmp_path / "claude_bin"
    claude_dir.mkdir()
    claude = claude_dir / "claude"
    claude.write_text("#!/bin/sh\nexit 0\n")
    claude.chmod(claude.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    env2 = {"PATH": str(claude_dir), "OPENAI_API_KEY": "k", "GEMINI_API_KEY": " "}

    entries2 = llm_endpoint.detect_providers(env=env2)
    by_name2 = _check_entries(entries2)
    available2 = sorted(n for n, e in by_name2.items() if field(e, "available"))
    assert available2 == ["claude-cli", "openai"]


def test_detect_providers_ollama_answering_with_short_timeout(tmp_path, monkeypatch):
    calls = []

    def answering_urlopen(*args, **kwargs):
        timeout = kwargs.get("timeout")
        if timeout is None and len(args) > 2:
            timeout = args[2]
        calls.append(timeout)
        return FakeResponse(json.dumps({"models": []}).encode("utf-8"))

    monkeypatch.setattr(urllib.request, "urlopen", answering_urlopen)
    empty_dir = tmp_path / "empty_bin"
    empty_dir.mkdir()
    env = {"PATH": str(empty_dir)}

    entries = llm_endpoint.detect_providers(env=env)
    by_name = _check_entries(entries)
    assert field(by_name["ollama"], "available") is True
    assert calls, "the Ollama probe did not call urlopen"
    for timeout in calls:
        assert timeout is not None
        assert 0 < float(timeout) <= 1.5


def _openai_reply():
    body = {
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
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    }
    return json.dumps(body).encode("utf-8")


def test_check_connection_ok_then_auth_no_log_unknown_provider(_isolate, monkeypatch):
    secret = "sk-test-secret-value-123456"
    monkeypatch.setenv("OPENAI_API_KEY", secret)

    def ok_urlopen(*args, **kwargs):
        return FakeResponse(_openai_reply())

    monkeypatch.setattr(urllib.request, "urlopen", ok_urlopen)
    ok = llm_endpoint.check_connection("openai", "m")
    assert field(ok, "ok") is True
    assert field(ok, "error") is None

    def unauthorized_urlopen(*args, **kwargs):
        request = args[0] if args else kwargs.get("url")
        url = getattr(request, "full_url", str(request))
        raise urllib.error.HTTPError(
            url, 401, "Unauthorized", {}, io.BytesIO(b'{"error": {"message": "bad key"}}')
        )

    monkeypatch.setattr(urllib.request, "urlopen", unauthorized_urlopen)
    bad = llm_endpoint.check_connection("openai", "m")
    assert field(bad, "ok") is False
    error = field(bad, "error")
    assert error is not None
    assert field(error, "category") == "auth"
    message = field(error, "message")
    assert isinstance(message, str)
    assert secret not in message
    assert secret not in json.dumps(bad, default=str) if isinstance(bad, dict) else True

    calls_dir = _isolate / ".hotdocs" / "calls"
    if calls_dir.exists():
        assert list(calls_dir.iterdir()) == []

    with pytest.raises(ValueError):
        llm_endpoint.check_connection("no-such-provider", "m")