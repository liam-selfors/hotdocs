# hotdocs-criterion: sha256:add06f0ff6d3abb0ea7808a110c77e8be3d6f9607a707c9f471261f60fb10822
import json
import os
import stat
import sys
import urllib.request

import pytest

import llm_endpoint


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write_fake_claude(bin_dir, log_path):
    bin_dir.mkdir(parents=True, exist_ok=True)
    script = bin_dir / "claude"
    assistant_event = {
        "type": "assistant",
        "message": {"content": [{"type": "text", "text": "hello from fake claude"}]},
    }
    result_event = {"type": "result", "is_error": False, "result": "hello from fake claude"}
    source = (
        "#!" + sys.executable + "\n"
        "import json, os, sys\n"
        "try:\n"
        "    sys.stdin.read()\n"
        "except Exception:\n"
        "    pass\n"
        "with open(" + repr(str(log_path)) + ", 'a') as f:\n"
        "    f.write(json.dumps({'argv': sys.argv[1:], "
        "'key': os.environ.get('ANTHROPIC_API_KEY')}) + '\\n')\n"
        "print(json.dumps(" + repr(assistant_event) + "))\n"
        "print(json.dumps(" + repr(result_event) + "))\n"
        "sys.stdout.flush()\n"
    )
    script.write_text(source)
    script.chmod(script.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return script


def _read_log(log_path):
    if not log_path.exists():
        return []
    return [json.loads(line) for line in log_path.read_text().splitlines() if line.strip()]


@pytest.mark.parametrize("key_set", [True, False])
def test_bare_claude_model_without_config_dispatches_through_claude_cli(
    tmp_path, monkeypatch, key_set
):
    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.chdir(work)
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)

    log_path = tmp_path / "claude_calls.log"
    bin_dir = tmp_path / "bin"
    _write_fake_claude(bin_dir, log_path)
    monkeypatch.setenv("PATH", str(bin_dir) + os.pathsep + os.environ.get("PATH", ""))

    if key_set:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-not-real")
    else:
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    assert not (work / "hotdocs.toml").exists()

    response = llm_endpoint.complete("Say hello", "claude-sonnet-5")

    assert field(response, "backend") == "claude-cli"
    assert field(response, "model") == "claude-sonnet-5"
    assert field(response, "model_call_error") is None
    assert field(response, "text") == "hello from fake claude"

    calls = _read_log(log_path)
    assert len(calls) == 1
    argv = calls[0]["argv"]

    assert "-p" in argv
    assert "--model" in argv
    assert argv[argv.index("--model") + 1] == "claude-sonnet-5"

    assert "--tools" in argv
    tools_index = argv.index("--tools")
    assert tools_index + 1 < len(argv)
    assert argv[tools_index + 1] == ""

    if key_set:
        assert "--bare" in argv
        assert "--safe-mode" not in argv
    else:
        assert "--safe-mode" in argv
        assert "--bare" not in argv


class _FakeResponse:
    def __init__(self, body):
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self, *args, **kwargs):
        return self._body

    def close(self):
        pass


_UNIVERSAL_BODY = json.dumps(
    {
        # anthropic Messages API
        "content": [{"type": "text", "text": "hi"}],
        "stop_reason": "end_turn",
        # openai / openai-compatible Chat Completions
        "choices": [{"index": 0, "message": {"role": "assistant", "content": "hi"}, "finish_reason": "stop"}],
        # gemini generateContent
        "candidates": [{"content": {"role": "model", "parts": [{"text": "hi"}]}}],
        # ollama chat / generate
        "message": {"role": "assistant", "content": "hi"},
        "response": "hi",
        "done": True,
    }
).encode("utf-8")


_EXPECTED = [
    ("anthropic:m", "anthropic", "https://api.anthropic.com"),
    ("openai:m", "openai", "https://api.openai.com/v1"),
    ("gemini:m", "gemini", "https://generativelanguage.googleapis.com"),
    ("ollama:m", "ollama", "http://localhost:11434"),
    ("openai-compatible:m", "openai-compatible", "http://h:8000/v1"),
]

_THIRD_PARTY_HTTP = {"requests", "httpx", "aiohttp", "urllib3", "anthropic", "openai", "google", "ollama"}


@pytest.mark.parametrize("model,provider,base", _EXPECTED)
def test_prefixed_models_dispatch_over_http_through_their_own_adapter(
    tmp_path, monkeypatch, model, provider, base
):
    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.chdir(work)
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    (work / "hotdocs.toml").write_text(
        "[llm]\n"
        "provider = " + json.dumps("openai-compatible") + "\n"
        "model = " + json.dumps("m") + "\n"
        "base_url = " + json.dumps("http://h:8000/v1") + "\n"
    )

    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-not-real")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-openai-test-not-real")
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-test-not-real")

    # A fake claude command, so any accidental dispatch to claude-cli is observable.
    claude_log = tmp_path / "claude_calls.log"
    bin_dir = tmp_path / "bin"
    _write_fake_claude(bin_dir, claude_log)
    monkeypatch.setenv("PATH", str(bin_dir) + os.pathsep + os.environ.get("PATH", ""))

    recorded = []

    def recorder(request, *args, **kwargs):
        url = request.full_url if isinstance(request, urllib.request.Request) else str(request)
        recorded.append(url)
        return _FakeResponse(_UNIVERSAL_BODY)

    monkeypatch.setattr(urllib.request, "urlopen", recorder)

    before_modules = set(sys.modules)
    response = llm_endpoint.complete("Say hi", model)
    new_modules = set(sys.modules) - before_modules

    assert field(response, "backend") == provider
    assert field(response, "model") == model

    assert len(recorded) >= 1
    for url in recorded:
        assert url.startswith(base), (url, base)

    assert _read_log(claude_log) == []

    loaded_top_levels = {name.split(".")[0] for name in new_modules}
    assert not (loaded_top_levels & _THIRD_PARTY_HTTP), loaded_top_levels