# hotdocs-criterion: sha256:564e6f4a84407f9f94b535ff8d1f6bb302be448d6753aeb72cfcd7d427296264
import json
import os
import stat
import sys
import urllib.request

import pytest

import llm_endpoint


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


THIRD_PARTY_HTTP_MODULES = [
    "requests",
    "httpx",
    "aiohttp",
    "urllib3",
    "anthropic",
    "openai",
    "google",
    "google.generativeai",
    "google.genai",
    "ollama",
    "litellm",
]


def _write_fake_claude(bin_dir, log_path):
    bin_dir.mkdir(parents=True, exist_ok=True)
    script_path = bin_dir / "claude"
    source = (
        "#!" + sys.executable + "\n"
        + "import json\n"
        + "import os\n"
        + "import sys\n"
        + "sys.stdin.read()\n"
        + "with open(" + repr(str(log_path)) + ", 'a') as fh:\n"
        + "    fh.write(json.dumps({'args': sys.argv[1:], "
        + "'key': os.environ.get('ANTHROPIC_API_KEY')}) + '\\n')\n"
        + "print(json.dumps({'type': 'assistant', 'message': "
        + "{'content': [{'type': 'text', 'text': 'hello from claude'}]}}))\n"
        + "print(json.dumps({'type': 'result', 'is_error': False, "
        + "'result': 'hello from claude'}))\n"
    )
    script_path.write_text(source)
    script_path.chmod(
        script_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
    )
    return script_path


def _read_log(log_path):
    if not log_path.exists():
        return []
    return [
        json.loads(line)
        for line in log_path.read_text().splitlines()
        if line.strip()
    ]


class _FakeResponse:
    def __init__(self, body):
        self._body = body
        self.status = 200
        self.code = 200
        self.headers = {"Content-Type": "application/json"}

    def read(self, *args, **kwargs):
        return self._body

    def getcode(self):
        return 200

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


# One body that satisfies every provider's reply shape at once.
_REPLY_BODY = json.dumps(
    {
        # anthropic Messages API
        "id": "msg_1",
        "type": "message",
        "role": "assistant",
        "content": [{"type": "text", "text": "ok"}],
        "stop_reason": "end_turn",
        # openai / openai-compatible Chat Completions
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": "ok"},
                "finish_reason": "stop",
            }
        ],
        # gemini generateContent
        "candidates": [
            {"content": {"role": "model", "parts": [{"text": "ok"}]}}
        ],
        # ollama /api/generate and /api/chat
        "response": "ok",
        "message": {"role": "assistant", "content": "ok"},
        "done": True,
    }
).encode("utf-8")


def _make_urlopen_recorder(calls):
    def fake_urlopen(request, *args, **kwargs):
        url = getattr(request, "full_url", None)
        if url is None:
            url = str(request)
        calls.append(url)
        return _FakeResponse(_REPLY_BODY)

    return fake_urlopen


@pytest.fixture
def isolated_cwd(tmp_path, monkeypatch):
    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.chdir(work)
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    return work


@pytest.mark.parametrize("key_set", [True, False])
def test_bare_claude_model_without_config_dispatches_through_claude_cli(
    tmp_path, isolated_cwd, monkeypatch, key_set
):
    assert not (isolated_cwd / "hotdocs.toml").exists()

    log_path = tmp_path / "claude_calls.log"
    bin_dir = tmp_path / "bin"
    _write_fake_claude(bin_dir, log_path)
    monkeypatch.setenv(
        "PATH", str(bin_dir) + os.pathsep + os.environ.get("PATH", "")
    )

    if key_set:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-anthropic")
    else:
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    http_calls = []
    monkeypatch.setattr(
        urllib.request, "urlopen", _make_urlopen_recorder(http_calls)
    )

    result = llm_endpoint.complete("Say hello", "claude-sonnet-5")

    entries = _read_log(log_path)
    assert len(entries) == 1, entries
    args = entries[0]["args"]

    assert "--tools" in args
    tools_index = args.index("--tools")
    assert tools_index + 1 < len(args)
    assert args[tools_index + 1] == ""

    if key_set:
        assert "--bare" in args
        assert "--safe-mode" not in args
    else:
        assert "--safe-mode" in args
        assert "--bare" not in args

    assert http_calls == []

    assert field(result, "backend") == "claude-cli"
    assert field(result, "model") == "claude-sonnet-5"
    assert field(result, "model_call_error") is None
    assert field(result, "text") == "hello from claude"


@pytest.mark.parametrize(
    "model, provider, expected_url_prefix",
    [
        ("anthropic:m", "anthropic", "https://api.anthropic.com"),
        ("openai:m", "openai", "https://api.openai.com/v1"),
        ("gemini:m", "gemini", "https://generativelanguage.googleapis.com"),
        ("ollama:m", "ollama", "http://localhost:11434"),
        ("openai-compatible:m", "openai-compatible", "http://h:8000/v1"),
    ],
)
def test_prefixed_models_dispatch_over_http_through_own_adapter(
    tmp_path, isolated_cwd, monkeypatch, model, provider, expected_url_prefix
):
    (isolated_cwd / "hotdocs.toml").write_text(
        "[llm]\n"
        + "provider = " + json.dumps("openai-compatible") + "\n"
        + "model = " + json.dumps("m") + "\n"
        + "base_url = " + json.dumps("http://h:8000/v1") + "\n"
    )

    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-anthropic")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-openai")
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini")

    # A claude command that would record any (wrong) dispatch to claude-cli.
    claude_log = tmp_path / "claude_calls.log"
    bin_dir = tmp_path / "bin"
    _write_fake_claude(bin_dir, claude_log)
    monkeypatch.setenv(
        "PATH", str(bin_dir) + os.pathsep + os.environ.get("PATH", "")
    )

    # Standard library only: any third-party HTTP/SDK import fails.
    for name in THIRD_PARTY_HTTP_MODULES:
        monkeypatch.setitem(sys.modules, name, None)

    http_calls = []
    monkeypatch.setattr(
        urllib.request, "urlopen", _make_urlopen_recorder(http_calls)
    )

    result = llm_endpoint.complete("Say ok", model)

    assert len(http_calls) == 1, http_calls
    assert http_calls[0].startswith(expected_url_prefix), http_calls[0]

    assert _read_log(claude_log) == []

    assert field(result, "backend") == provider
    assert field(result, "model") == model
    assert field(result, "model_call_error") is None
    assert field(result, "text") == "ok"