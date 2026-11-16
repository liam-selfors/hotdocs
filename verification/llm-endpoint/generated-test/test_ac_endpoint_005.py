import json
import os
import stat
import sys
import urllib.request

import pytest

import llm_endpoint


def _field(value, name):
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def _write_fake_claude(bin_dir, log_path):
    bin_dir.mkdir(parents=True, exist_ok=True)
    script = bin_dir / "claude"
    script.write_text(
        "#!" + sys.executable + "\n"
        "import json, sys\n"
        "with open(" + repr(str(log_path)) + ", 'a') as f:\n"
        "    f.write(json.dumps(sys.argv[1:]) + '\\n')\n"
        "print(json.dumps({'type': 'system', 'subtype': 'init'}))\n"
        "print(json.dumps({'type': 'assistant', 'message': {'role': 'assistant', "
        "'content': [{'type': 'text', 'text': 'recorded reply'}]}}))\n"
        "print(json.dumps({'type': 'result', 'subtype': 'success', 'is_error': False, "
        "'result': 'recorded reply'}))\n"
        "sys.stdout.flush()\n"
    )
    mode = script.stat().st_mode
    script.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return script


def _read_invocations(log_path):
    if not log_path.exists():
        return []
    out = []
    for line in log_path.read_text().splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


def _has_empty_tools(argv):
    for i, arg in enumerate(argv):
        if arg == "--tools" and i + 1 < len(argv) and argv[i + 1] == "":
            return True
        if arg == "--tools=" or arg == '--tools=""':
            return True
    return False


_ONLY_INFO_FLAGS = {"--version", "-v", "--help", "-h"}


def _dispatch_invocations(invocations):
    return [
        argv for argv in invocations
        if not (argv and set(argv) <= _ONLY_INFO_FLAGS)
    ]


class _FakeResponse:
    def __init__(self, body):
        self._body = body
        self.status = 200
        self.code = 200
        self.headers = {"Content-Type": "application/json"}

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self, *args, **kwargs):
        return self._body

    def getcode(self):
        return 200

    def close(self):
        pass


_UNION_BODY = json.dumps(
    {
        "id": "x",
        "type": "message",
        "role": "assistant",
        "content": [{"type": "text", "text": "ok"}],
        "stop_reason": "end_turn",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": "ok"},
                "finish_reason": "stop",
            }
        ],
        "candidates": [
            {"content": {"role": "model", "parts": [{"text": "ok"}]}}
        ],
        "message": {"role": "assistant", "content": "ok"},
        "response": "ok",
        "done": True,
    }
).encode("utf-8")


def _request_url(req):
    if hasattr(req, "full_url"):
        return req.full_url
    if hasattr(req, "get_full_url"):
        return req.get_full_url()
    return str(req)


def _base_env(monkeypatch, tmp_path):
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.chdir(work)
    return work


@pytest.mark.parametrize("key_set", [True, False])
def test_bare_claude_model_without_config_dispatches_through_claude_cli(
    tmp_path, monkeypatch, key_set
):
    work = _base_env(monkeypatch, tmp_path)
    assert not (work / "hotdocs.toml").exists()

    log_path = tmp_path / "claude_invocations.jsonl"
    bin_dir = tmp_path / "bin"
    _write_fake_claude(bin_dir, log_path)
    monkeypatch.setenv("PATH", str(bin_dir) + os.pathsep + os.environ.get("PATH", ""))

    if key_set:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-not-a-real-key")
    else:
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    http_calls = []

    def recording_urlopen(request, *args, **kwargs):
        http_calls.append(_request_url(request))
        return _FakeResponse(_UNION_BODY)

    monkeypatch.setattr(urllib.request, "urlopen", recording_urlopen)

    result = llm_endpoint.complete("Say hello.", "claude-sonnet-5")

    assert _field(result, "backend") == "claude-cli"
    assert _field(result, "model") == "claude-sonnet-5"
    assert http_calls == []

    invocations = _dispatch_invocations(_read_invocations(log_path))
    assert len(invocations) >= 1, "the claude command was never invoked"

    expected_flag = "--bare" if key_set else "--safe-mode"
    forbidden_flag = "--safe-mode" if key_set else "--bare"
    for argv in invocations:
        assert _has_empty_tools(argv), argv
        assert expected_flag in argv, argv
        assert forbidden_flag not in argv, argv


_EXPECTED_HOSTS = {
    "anthropic": "api.anthropic.com",
    "openai": "api.openai.com",
    "gemini": "generativelanguage.googleapis.com",
    "ollama": "localhost:11434",
    "openai-compatible": "h:8000",
}

_THIRD_PARTY_HTTP_MODULES = (
    "requests",
    "httpx",
    "aiohttp",
    "urllib3",
    "anthropic",
    "openai",
    "google.generativeai",
    "google.genai",
    "ollama",
    "litellm",
)


@pytest.mark.parametrize(
    "provider",
    ["anthropic", "openai", "gemini", "ollama", "openai-compatible"],
)
def test_prefixed_models_dispatch_over_http_through_own_adapter(
    tmp_path, monkeypatch, provider
):
    work = _base_env(monkeypatch, tmp_path)
    (work / "hotdocs.toml").write_text(
        "[llm]\n"
        'provider = "openai-compatible"\n'
        'model = "m"\n'
        'base_url = "http://h:8000/v1"\n'
    )

    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-not-real")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-openai-test-not-real")
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-test-not-real")

    log_path = tmp_path / "claude_invocations.jsonl"
    bin_dir = tmp_path / "bin"
    _write_fake_claude(bin_dir, log_path)
    monkeypatch.setenv("PATH", str(bin_dir) + os.pathsep + os.environ.get("PATH", ""))

    http_calls = []

    def recording_urlopen(request, *args, **kwargs):
        http_calls.append(_request_url(request))
        return _FakeResponse(_UNION_BODY)

    monkeypatch.setattr(urllib.request, "urlopen", recording_urlopen)

    preexisting = set(sys.modules)

    model = provider + ":m"
    result = llm_endpoint.complete("Say hello.", model)

    assert _field(result, "backend") == provider
    assert _field(result, "model") == model

    assert len(http_calls) >= 1, "no HTTP request was made through urllib.request.urlopen"
    expected_host = _EXPECTED_HOSTS[provider]
    assert any(expected_host in url for url in http_calls), http_calls
    for other, host in _EXPECTED_HOSTS.items():
        if other == provider:
            continue
        assert not any(host in url for url in http_calls), (provider, http_calls)

    assert _dispatch_invocations(_read_invocations(log_path)) == []

    newly_loaded = set(sys.modules) - preexisting
    for name in _THIRD_PARTY_HTTP_MODULES:
        assert name not in newly_loaded, (
            "non-standard-library module %r was imported during dispatch" % name
        )