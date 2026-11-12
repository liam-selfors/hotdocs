import email.message
import io
import json
import os
import stat
import sys
import urllib.error
import urllib.request

import pytest

import llm_endpoint


EXPECTED_PROVIDERS = {
    "claude-cli",
    "anthropic",
    "openai",
    "openai-compatible",
    "gemini",
    "ollama",
}

ENTRY_KEYS = ("provider", "available", "reason", "suggested_model", "api_key_env")


def _get(value, key, default=None):
    if isinstance(value, dict):
        return value.get(key, default)
    return getattr(value, key, default)


def _has(value, key):
    if isinstance(value, dict):
        return key in value
    return hasattr(value, key)


class _FakeReply:
    def __init__(self, body: bytes):
        self._body = body
        self.status = 200
        self.code = 200

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


def _request_url(request):
    if isinstance(request, str):
        return request
    full = getattr(request, "full_url", None)
    if full is not None:
        return full
    get_full = getattr(request, "get_full_url", None)
    if callable(get_full):
        return get_full()
    return str(request)


def _empty_bin_dir(tmp_path, name):
    d = tmp_path / name
    d.mkdir()
    return d


def _make_claude_executable(directory):
    names = ["claude"]
    if os.name == "nt":
        names += ["claude.exe", "claude.cmd", "claude.bat"]
    for n in names:
        p = directory / n
        p.write_text("#!/bin/sh\nexit 0\n")
        mode = os.stat(p).st_mode
        os.chmod(p, mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH | stat.S_IRUSR)


def _raising_urlopen(calls=None):
    def fake(request, *args, **kwargs):
        if calls is not None:
            calls.append({"url": _request_url(request), "args": args, "kwargs": kwargs})
        raise urllib.error.URLError(ConnectionRefusedError(111, "Connection refused"))

    return fake


def _entries_by_provider(result):
    assert isinstance(result, list), f"detect_providers must return a list, got {type(result)!r}"
    by_name = {}
    for entry in result:
        for key in ENTRY_KEYS:
            assert _has(entry, key), f"entry {entry!r} missing key {key!r}"
        name = _get(entry, "provider")
        assert name not in by_name, f"duplicate entry for provider {name!r}"
        by_name[name] = entry
    return by_name


def _isolate_env(monkeypatch, tmp_path):
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    work = tmp_path / "work"
    work.mkdir(exist_ok=True)
    monkeypatch.chdir(work)
    return work


def test_providers_names_match_contract():
    names = set(llm_endpoint.PROVIDERS.keys())
    assert names == EXPECTED_PROVIDERS


def test_detect_providers_one_entry_per_provider_only_openai_available(monkeypatch, tmp_path):
    _isolate_env(monkeypatch, tmp_path)
    calls = []
    monkeypatch.setattr(urllib.request, "urlopen", _raising_urlopen(calls))
    # Make sure the real process env would mislead if consulted.
    monkeypatch.setenv("ANTHROPIC_API_KEY", "real-env-anthropic-key")
    monkeypatch.setenv("GEMINI_API_KEY", "real-env-gemini-key")

    bin_dir = _empty_bin_dir(tmp_path, "nobin")
    env = {"PATH": str(bin_dir), "OPENAI_API_KEY": "k", "GEMINI_API_KEY": " "}

    result = llm_endpoint.detect_providers(env=env)
    by_name = _entries_by_provider(result)

    assert set(by_name.keys()) == set(llm_endpoint.PROVIDERS.keys())
    assert len(result) == len(llm_endpoint.PROVIDERS)

    available = {name for name, entry in by_name.items() if _get(entry, "available") is True}
    assert available == {"openai"}, f"expected only openai available, got {available!r}"

    for name, entry in by_name.items():
        assert isinstance(_get(entry, "available"), bool)
        reason = _get(entry, "reason")
        assert isinstance(reason, str)
        assert "k" != reason
        expected_suggestion = llm_endpoint.PROVIDERS[name]
        expected_suggestion = _get(expected_suggestion, "suggested_model")
        assert _get(entry, "suggested_model") == expected_suggestion

    assert _get(by_name["openai"], "api_key_env") == "OPENAI_API_KEY"
    assert _get(by_name["gemini"], "api_key_env") == "GEMINI_API_KEY"
    assert _get(by_name["anthropic"], "api_key_env") == "ANTHROPIC_API_KEY"


def test_detect_providers_claude_on_path_makes_claude_cli_available(monkeypatch, tmp_path):
    _isolate_env(monkeypatch, tmp_path)
    monkeypatch.setattr(urllib.request, "urlopen", _raising_urlopen())

    bin_dir = _empty_bin_dir(tmp_path, "withclaude")
    _make_claude_executable(bin_dir)
    env = {"PATH": str(bin_dir), "OPENAI_API_KEY": "k", "GEMINI_API_KEY": " "}

    result = llm_endpoint.detect_providers(env=env)
    by_name = _entries_by_provider(result)
    assert set(by_name.keys()) == set(llm_endpoint.PROVIDERS.keys())

    available = {name for name, entry in by_name.items() if _get(entry, "available") is True}
    assert available == {"openai", "claude-cli"}, f"got {available!r}"


def test_detect_providers_ollama_available_when_probe_answers(monkeypatch, tmp_path):
    _isolate_env(monkeypatch, tmp_path)
    calls = []

    def fake_urlopen(request, *args, **kwargs):
        calls.append({"url": _request_url(request), "args": args, "kwargs": kwargs})
        return _FakeReply(json.dumps({"models": [{"name": "llama3.2:latest"}]}).encode())

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    bin_dir = _empty_bin_dir(tmp_path, "nobin2")
    env = {"PATH": str(bin_dir)}

    result = llm_endpoint.detect_providers(env=env)
    by_name = _entries_by_provider(result)

    assert _get(by_name["ollama"], "available") is True

    probe_calls = [c for c in calls if c["url"].rstrip("/").endswith("/api/tags")]
    assert probe_calls, f"expected a probe to /api/tags, saw {[c['url'] for c in calls]!r}"
    for c in probe_calls:
        timeout = c["kwargs"].get("timeout")
        if timeout is None and len(c["args"]) >= 2:
            timeout = c["args"][1]
        assert timeout is not None, "Ollama probe must pass an explicit timeout"
        assert float(timeout) <= 1.5, f"probe timeout {timeout!r} exceeds about a second"


_OPENAI_SUCCESS_BODY = json.dumps(
    {
        "id": "chatcmpl-test",
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
        "output_text": "ok",
        "output": [
            {
                "type": "message",
                "role": "assistant",
                "content": [{"type": "output_text", "text": "ok"}],
            }
        ],
    }
).encode()


def _calls_dir_entries(work):
    calls_dir = work / ".hotdocs" / "calls"
    if not calls_dir.exists():
        return []
    return [p for p in calls_dir.rglob("*") if p.is_file()]


def test_check_connection_success_then_auth_failure_and_no_call_log(monkeypatch, tmp_path):
    work = _isolate_env(monkeypatch, tmp_path)
    secret = "sk-test-SECRETVALUE-0123456789"
    monkeypatch.setenv("OPENAI_API_KEY", secret)

    calls = []

    def ok_urlopen(request, *args, **kwargs):
        calls.append(_request_url(request))
        return _FakeReply(_OPENAI_SUCCESS_BODY)

    monkeypatch.setattr(urllib.request, "urlopen", ok_urlopen)
    result = llm_endpoint.check_connection("openai", "m")
    assert calls, "check_connection must make a real (here: faked) HTTP request"
    assert _get(result, "ok") is True
    assert _get(result, "error") is None
    assert _calls_dir_entries(work) == []

    def auth_fail_urlopen(request, *args, **kwargs):
        url = _request_url(request)
        calls.append(url)
        hdrs = email.message.Message()
        raise urllib.error.HTTPError(
            url,
            401,
            "Unauthorized",
            hdrs,
            io.BytesIO(b'{"error": {"message": "Incorrect API key provided", "type": "invalid_request_error"}}'),
        )

    monkeypatch.setattr(urllib.request, "urlopen", auth_fail_urlopen)
    result = llm_endpoint.check_connection("openai", "m")
    assert _get(result, "ok") is False
    error = _get(result, "error")
    assert error is not None
    assert _get(error, "category") == "auth"
    message = _get(error, "message")
    assert isinstance(message, str)
    assert secret not in message
    assert secret not in repr(result)

    assert _calls_dir_entries(work) == [], "check_connection must never write a call-log record"


def test_check_connection_unknown_provider_raises_value_error(monkeypatch, tmp_path):
    _isolate_env(monkeypatch, tmp_path)
    monkeypatch.setenv("OPENAI_API_KEY", "k")

    def must_not_call(request, *args, **kwargs):
        raise AssertionError("no request expected for an unknown provider")

    monkeypatch.setattr(urllib.request, "urlopen", must_not_call)
    with pytest.raises(ValueError):
        llm_endpoint.check_connection("no-such-provider", "m")