# hotdocs-criterion: sha256:9d4124d68e671b0deeefb5d12e05db0177568ce56461753b1bc9e1233e56e6db
"""AC-ENDPOINT-005 (Covers: R-ENDPOINT-003).

Given no hotdocs.toml, and the claude command replaced by a recorder,
complete() with a bare "claude-sonnet-5" and no provider-selection parameter
dispatches through claude-cli, passing --tools "" and one of --bare
(ANTHROPIC_API_KEY set) or --safe-mode (not set).

Given each of "anthropic:m", "openai:m", "gemini:m", "ollama:m" and
"openai-compatible:m", under a hotdocs.toml whose [llm] table is provider
"openai-compatible", model "m", base_url "http://h:8000/v1", with
urllib.request.urlopen replaced by a recorder and the three API keys set,
each dispatches over HTTP through its own adapter, using only the standard
library.
"""

import json
import os
import stat
import sys
import urllib.request

import pytest

import llm_endpoint


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


# --------------------------------------------------------------------------
# Fixtures and helpers
# --------------------------------------------------------------------------


def _write_fake_claude(bin_dir, log_path):
    script = (
        "#!" + sys.executable + "\n"
        "import json, os, sys\n"
        "data = ''\n"
        "try:\n"
        "    data = sys.stdin.read()\n"
        "except Exception:\n"
        "    data = ''\n"
        "with open(" + repr(str(log_path)) + ", 'a') as fh:\n"
        "    fh.write(json.dumps({'argv': sys.argv[1:],\n"
        "                         'anthropic_api_key': os.environ.get('ANTHROPIC_API_KEY'),\n"
        "                         'stdin': data}) + '\\n')\n"
        "print(json.dumps({'type': 'system', 'subtype': 'init'}))\n"
        "print(json.dumps({'type': 'assistant', 'message': {'role': 'assistant',\n"
        "    'content': [{'type': 'text', 'text': 'ok'}]}}))\n"
        "print(json.dumps({'type': 'result', 'subtype': 'success',\n"
        "    'is_error': False, 'result': 'ok'}))\n"
    )
    path = bin_dir / "claude"
    path.write_text(script)
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return path


def _read_claude_log(log_path):
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
        self.headers = {}

    def read(self, *args, **kwargs):
        return self._body

    def getcode(self):
        return 200

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


# One body every supported wire format can read a reply from.
_COMBINED_BODY = json.dumps(
    {
        # anthropic Messages API
        "id": "x",
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
        # ollama /api/chat and /api/generate
        "message": {"role": "assistant", "content": "ok"},
        "response": "ok",
        "done": True,
    }
).encode("utf-8")


def _install_urlopen_recorder(monkeypatch, calls):
    def fake_urlopen(request, *args, **kwargs):
        url = getattr(request, "full_url", None)
        if url is None:
            url = str(request)
        calls.append(
            {
                "url": url,
                "method": request.get_method()
                if hasattr(request, "get_method")
                else None,
            }
        )
        return _FakeResponse(_COMBINED_BODY)

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)


@pytest.fixture
def env(tmp_path, monkeypatch):
    workdir = tmp_path / "work"
    workdir.mkdir()
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log_path = tmp_path / "claude_calls.jsonl"
    _write_fake_claude(bin_dir, log_path)

    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    monkeypatch.chdir(workdir)
    monkeypatch.setenv(
        "PATH", str(bin_dir) + os.pathsep + os.environ.get("PATH", "")
    )
    return {"workdir": workdir, "log_path": log_path}


# --------------------------------------------------------------------------
# Scenario 1: bare claude model, no hotdocs.toml -> claude-cli
# --------------------------------------------------------------------------


@pytest.mark.parametrize("key_set", [True, False], ids=["key-set", "key-unset"])
def test_bare_claude_model_without_config_dispatches_through_claude_cli(
    env, monkeypatch, key_set
):
    assert not (env["workdir"] / "hotdocs.toml").exists()

    if key_set:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-not-a-real-key")
    else:
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    http_calls = []
    _install_urlopen_recorder(monkeypatch, http_calls)

    result = llm_endpoint.complete("Say ok.", "claude-sonnet-5")

    assert field(result, "backend") == "claude-cli"
    assert field(result, "model_call_error") is None
    assert field(result, "text") == "ok"
    assert http_calls == [], "claude-cli must not go over HTTP"

    invocations = _read_claude_log(env["log_path"])
    assert len(invocations) == 1, invocations
    argv = invocations[0]["argv"]

    assert "--tools" in argv, argv
    tools_index = argv.index("--tools")
    assert tools_index + 1 < len(argv), argv
    assert argv[tools_index + 1] == "", argv

    if key_set:
        assert "--bare" in argv, argv
        assert "--safe-mode" not in argv, argv
    else:
        assert "--safe-mode" in argv, argv
        assert "--bare" not in argv, argv


# --------------------------------------------------------------------------
# Scenario 2: each prefixed HTTP provider dispatches through its own adapter
# --------------------------------------------------------------------------


_HTTP_CASES = [
    ("anthropic:m", "anthropic", "https://api.anthropic.com", "messages"),
    ("openai:m", "openai", "https://api.openai.com/v1", "chat/completions"),
    (
        "gemini:m",
        "gemini",
        "https://generativelanguage.googleapis.com",
        "generateContent",
    ),
    ("ollama:m", "ollama", "http://localhost:11434", "/api/"),
    (
        "openai-compatible:m",
        "openai-compatible",
        "http://h:8000/v1",
        "chat/completions",
    ),
]


def _top_level(name):
    return name.split(".", 1)[0]


@pytest.mark.parametrize(
    "model,provider,base,path_marker",
    _HTTP_CASES,
    ids=[case[1] for case in _HTTP_CASES],
)
def test_each_http_provider_dispatches_through_its_own_adapter(
    env, monkeypatch, model, provider, base, path_marker
):
    (env["workdir"] / "hotdocs.toml").write_text(
        "[llm]\n"
        'provider = "openai-compatible"\n'
        'model = "m"\n'
        'base_url = "http://h:8000/v1"\n'
    )
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-not-real")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-openai-test-not-real")
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-test-not-real")

    http_calls = []
    _install_urlopen_recorder(monkeypatch, http_calls)

    modules_before = set(sys.modules)
    result = llm_endpoint.complete("Say ok.", model)
    modules_after = set(sys.modules)

    assert field(result, "backend") == provider
    assert field(result, "model") == model
    assert field(result, "model_call_error") is None, field(
        result, "model_call_error"
    )
    assert field(result, "text") == "ok"

    # Dispatched over HTTP via urllib.request.urlopen, to its own endpoint.
    assert len(http_calls) >= 1, "expected an HTTP call through urlopen"
    url = http_calls[-1]["url"]
    assert url.startswith(base), (provider, url)
    assert path_marker in url, (provider, url)

    # Never through the claude command.
    assert _read_claude_log(env["log_path"]) == []

    # No dependency beyond the standard library was pulled in by the call.
    stdlib = getattr(sys, "stdlib_module_names", None)
    if stdlib is not None:
        new_top = {_top_level(name) for name in modules_after - modules_before}
        foreign = sorted(
            name
            for name in new_top
            if name not in stdlib
            and not name.startswith("_")
            and "llm_endpoint" not in name
        )
        assert foreign == [], f"non-stdlib modules imported: {foreign}"