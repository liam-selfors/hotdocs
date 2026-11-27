# hotdocs-criterion: sha256:dbd087970bb72e4acb8b3a9297c000fbe6cb12306d8e599aa9e1e9eb7c693e9b
import ast
import json
import os
import stat
import sys
import urllib.request
from pathlib import Path

import pytest

import llm_endpoint


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


STREAM_EVENTS = (
    json.dumps({"type": "system", "subtype": "init"})
    + "\n"
    + json.dumps(
        {
            "type": "assistant",
            "message": {"content": [{"type": "text", "text": "hello from fake claude"}]},
        }
    )
    + "\n"
    + json.dumps(
        {
            "type": "result",
            "subtype": "success",
            "is_error": False,
            "result": "hello from fake claude",
        }
    )
    + "\n"
)


def _write_fake_claude(bin_dir, log_path):
    bin_dir.mkdir(parents=True, exist_ok=True)
    script = bin_dir / "claude"
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
        "sys.stdout.write(" + repr(STREAM_EVENTS) + ")\n"
        "sys.stdout.flush()\n"
    )
    script.write_text(source)
    script.chmod(script.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return script


def _read_log(log_path):
    if not log_path.exists():
        return []
    return [json.loads(line) for line in log_path.read_text().splitlines() if line.strip()]


class _FakeResponse:
    def __init__(self, body):
        self._body = body
        self.status = 200

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self, *args, **kwargs):
        return self._body

    def getcode(self):
        return 200


# A reply body carrying each provider's documented success shape, so
# every adapter finds its own text in it.
COMBINED_BODY = json.dumps(
    {
        "id": "x",
        "type": "message",
        "role": "assistant",
        "stop_reason": "end_turn",
        "content": [{"type": "text", "text": "ok"}],
        "choices": [
            {"index": 0, "message": {"role": "assistant", "content": "ok"}, "finish_reason": "stop"}
        ],
        "candidates": [{"content": {"role": "model", "parts": [{"text": "ok"}]}}],
        "message": {"role": "assistant", "content": "ok"},
        "response": "ok",
        "done": True,
    }
).encode("utf-8")


def _install_urlopen_recorder(monkeypatch):
    calls = []

    def fake_urlopen(request, *args, **kwargs):
        if isinstance(request, urllib.request.Request):
            url = request.full_url
        else:
            url = str(request)
        calls.append({"url": url, "request": request})
        return _FakeResponse(COMBINED_BODY)

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    return calls


@pytest.fixture
def fresh_cwd(tmp_path, monkeypatch):
    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.chdir(work)
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    return work


@pytest.mark.parametrize("key_set", [True, False])
def test_bare_model_without_config_dispatches_through_claude_cli(
    tmp_path, fresh_cwd, monkeypatch, key_set
):
    log_path = tmp_path / "claude_calls.log"
    bin_dir = tmp_path / "bin"
    _write_fake_claude(bin_dir, log_path)
    monkeypatch.setenv("PATH", str(bin_dir) + os.pathsep + os.environ.get("PATH", ""))
    if key_set:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-not-real")
    else:
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    http_calls = _install_urlopen_recorder(monkeypatch)

    assert not (fresh_cwd / "hotdocs.toml").exists()

    result = llm_endpoint.complete("Say hello.", "claude-sonnet-5")

    assert field(result, "backend") == "claude-cli"
    assert field(result, "model") == "claude-sonnet-5"
    assert field(result, "model_call_error") is None
    assert field(result, "text") == "hello from fake claude"
    assert http_calls == []

    records = _read_log(log_path)
    assert len(records) == 1
    argv = records[0]["argv"]

    assert "--tools" in argv
    idx = argv.index("--tools")
    assert idx + 1 < len(argv)
    assert argv[idx + 1] == ""

    if key_set:
        assert "--bare" in argv
        assert "--safe-mode" not in argv
    else:
        assert "--safe-mode" in argv
        assert "--bare" not in argv


EXPECTED = {
    "anthropic:m": ("anthropic", "api.anthropic.com"),
    "openai:m": ("openai", "api.openai.com"),
    "gemini:m": ("gemini", "generativelanguage.googleapis.com"),
    "ollama:m": ("ollama", "localhost:11434"),
    "openai-compatible:m": ("openai-compatible", "h:8000"),
}


@pytest.mark.parametrize("model", sorted(EXPECTED))
def test_each_http_provider_dispatches_through_its_own_adapter(
    tmp_path, fresh_cwd, monkeypatch, model
):
    (fresh_cwd / "hotdocs.toml").write_text(
        "[llm]\n"
        'provider = "openai-compatible"\n'
        'model = "m"\n'
        'base_url = "http://h:8000/v1"\n'
    )
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-not-real")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-openai-test-not-real")
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-test-not-real")

    # Make sure no claude command is consulted for the HTTP providers.
    log_path = tmp_path / "claude_calls.log"
    bin_dir = tmp_path / "bin"
    _write_fake_claude(bin_dir, log_path)
    monkeypatch.setenv("PATH", str(bin_dir) + os.pathsep + os.environ.get("PATH", ""))

    calls = _install_urlopen_recorder(monkeypatch)

    result = llm_endpoint.complete("Say ok.", model)

    provider, host = EXPECTED[model]
    assert field(result, "backend") == provider
    assert field(result, "model") == model
    assert field(result, "model_call_error") is None
    assert field(result, "text") == "ok"

    assert len(calls) >= 1
    assert any(host in c["url"] for c in calls), [c["url"] for c in calls]
    assert _read_log(log_path) == []


def _module_source_files():
    path = Path(llm_endpoint.__file__).resolve()
    if path.name == "__init__.py":
        return sorted(path.parent.rglob("*.py"))
    return [path]


def test_http_providers_add_no_dependency_beyond_standard_library():
    stdlib = set(getattr(sys, "stdlib_module_names", ()))
    if not stdlib:
        pytest.skip("sys.stdlib_module_names unavailable")
    own = {"llm_endpoint"}
    offenders = []
    for file in _module_source_files():
        tree = ast.parse(file.read_text(), filename=str(file))
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                if node.level and node.level > 0:
                    continue
                if node.module:
                    names = [node.module]
            for name in names:
                top = name.split(".")[0]
                if top in stdlib or top in own or top == "__future__":
                    continue
                offenders.append((str(file), name))
    assert offenders == []