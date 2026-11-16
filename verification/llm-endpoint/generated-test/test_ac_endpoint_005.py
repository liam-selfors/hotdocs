"""AC-ENDPOINT-005 (Covers: R-ENDPOINT-003).

Part 1: with no hotdocs.toml and the `claude` command replaced by a
recorder, a bare `claude-sonnet-5` with no provider-selection parameter
dispatches through claude-cli, passing `--tools ""` and exactly one of
`--bare` (ANTHROPIC_API_KEY set) or `--safe-mode` (not set).

Part 2: each prefixed model (`anthropic:m`, `openai:m`, `gemini:m`,
`ollama:m`, `openai-compatible:m`), with a hotdocs.toml configuring
openai-compatible at http://h:8000/v1, dispatches over HTTP through its
own adapter via `urllib.request.urlopen`, with no dependency beyond the
standard library.
"""

import json
import os
import stat
import sys
import urllib.parse
import urllib.request
from pathlib import Path

import pytest

import llm_endpoint


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


_FAKE_CLAUDE_PY = r'''
import json
import sys

with open(__LOG__, "a", encoding="utf-8") as fh:
    fh.write(json.dumps(sys.argv[1:]) + "\n")

assistant = {
    "type": "assistant",
    "message": {
        "role": "assistant",
        "content": [{"type": "text", "text": "recorded reply"}],
    },
}
result = {
    "type": "result",
    "subtype": "success",
    "is_error": False,
    "result": "recorded reply",
}
sys.stdout.write(json.dumps(assistant) + "\n")
sys.stdout.write(json.dumps(result) + "\n")
sys.stdout.flush()
sys.exit(0)
'''


def _install_fake_claude(tmp_path, monkeypatch):
    """Put a recording `claude` command first on PATH; return its log path."""
    bin_dir = tmp_path / "fakebin"
    bin_dir.mkdir()
    log = tmp_path / "claude_calls.jsonl"
    script = tmp_path / "fake_claude_impl.py"
    script.write_text(
        _FAKE_CLAUDE_PY.replace("__LOG__", repr(str(log))), encoding="utf-8"
    )
    wrapper = bin_dir / "claude"
    wrapper.write_text(
        "#!/bin/sh\n" f'exec "{sys.executable}" "{script}" "$@"\n',
        encoding="utf-8",
    )
    wrapper.chmod(
        wrapper.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
    )
    monkeypatch.setenv(
        "PATH", str(bin_dir) + os.pathsep + os.environ.get("PATH", "")
    )
    return log


def _read_claude_calls(log):
    if not log.exists():
        return []
    return [
        json.loads(line)
        for line in log.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _fresh_workdir(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.chdir(work)
    return work


class _FakeReply:
    def __init__(self, body):
        self._body = body
        self.status = 200
        self.code = 200

    def read(self, *args, **kwargs):
        return self._body

    def getcode(self):
        return 200

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


# One reply body that every provider's wire format can read its text from.
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
        # ollama /api/chat and /api/generate
        "message": {"role": "assistant", "content": "ok"},
        "response": "ok",
        "done": True,
    }
).encode("utf-8")


def _request_url(request):
    if hasattr(request, "full_url"):
        return request.full_url
    if hasattr(request, "get_full_url"):
        return request.get_full_url()
    return str(request)


def _install_urlopen_recorder(monkeypatch):
    calls = []

    def fake_urlopen(request, *args, **kwargs):
        calls.append(_request_url(request))
        return _FakeReply(_REPLY_BODY)

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    return calls


# ---------------------------------------------------------------------------
# Part 1: bare claude-sonnet-5 -> claude-cli
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("api_key_set", [True, False], ids=["key-set", "key-unset"])
def test_bare_claude_model_dispatches_through_claude_cli(
    tmp_path, monkeypatch, api_key_set
):
    work = _fresh_workdir(tmp_path, monkeypatch)
    assert not (work / "hotdocs.toml").exists()
    log = _install_fake_claude(tmp_path, monkeypatch)
    http_calls = _install_urlopen_recorder(monkeypatch)

    if api_key_set:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-not-a-real-key")
    else:
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    response = llm_endpoint.complete("Say hello.", "claude-sonnet-5")

    assert field(response, "backend") == "claude-cli"
    assert http_calls == [], "claude-cli must not dispatch over HTTP"

    calls = _read_claude_calls(log)
    assert len(calls) >= 1, "the claude command was never invoked"

    for argv in calls:
        has_empty_tools = any(
            (arg == "--tools" and i + 1 < len(argv) and argv[i + 1] == "")
            or arg == "--tools="
            for i, arg in enumerate(argv)
        )
        assert has_empty_tools, f'--tools "" missing from {argv!r}'

        if api_key_set:
            assert "--bare" in argv, f"--bare missing from {argv!r}"
            assert "--safe-mode" not in argv, f"unexpected --safe-mode in {argv!r}"
        else:
            assert "--safe-mode" in argv, f"--safe-mode missing from {argv!r}"
            assert "--bare" not in argv, f"unexpected --bare in {argv!r}"


# ---------------------------------------------------------------------------
# Part 2: prefixed models -> their own HTTP adapters, stdlib only
# ---------------------------------------------------------------------------

_HTTP_CASES = [
    # (model string, expected backend, expected scheme://netloc, path fragment)
    ("anthropic:m", "anthropic", "https://api.anthropic.com", "/messages"),
    ("openai:m", "openai", "https://api.openai.com", "/chat/completions"),
    (
        "gemini:m",
        "gemini",
        "https://generativelanguage.googleapis.com",
        "generateContent",
    ),
    ("ollama:m", "ollama", "http://localhost:11434", "/api/"),
    ("openai-compatible:m", "openai-compatible", "http://h:8000", "/v1/chat/completions"),
]

_THIRD_PARTY_HTTP = {
    "requests",
    "httpx",
    "aiohttp",
    "urllib3",
    "anthropic",
    "openai",
    "google",
    "ollama",
    "litellm",
}


def _new_third_party_modules(before):
    stdlib = getattr(sys, "stdlib_module_names", None)
    bad = []
    for name in set(sys.modules) - before:
        top = name.split(".")[0]
        if top.startswith("llm_endpoint"):
            continue
        if top in _THIRD_PARTY_HTTP:
            bad.append(name)
            continue
        if stdlib is not None and top in stdlib:
            continue
        mod = sys.modules.get(name)
        path = str(getattr(mod, "__file__", None) or "")
        if "site-packages" in path or "dist-packages" in path:
            bad.append(name)
    return sorted(bad)


@pytest.mark.parametrize(
    "model, backend, origin, path_fragment",
    _HTTP_CASES,
    ids=[c[0] for c in _HTTP_CASES],
)
def test_prefixed_models_dispatch_over_http_through_own_adapter(
    tmp_path, monkeypatch, model, backend, origin, path_fragment
):
    work = _fresh_workdir(tmp_path, monkeypatch)
    (work / "hotdocs.toml").write_text(
        "[llm]\n"
        'provider = "openai-compatible"\n'
        'model = "m"\n'
        'base_url = "http://h:8000/v1"\n',
        encoding="utf-8",
    )
    claude_log = _install_fake_claude(tmp_path, monkeypatch)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-not-real")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-openai-test-not-real")
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-test-not-real")
    calls = _install_urlopen_recorder(monkeypatch)

    modules_before = set(sys.modules)
    response = llm_endpoint.complete("Say hello.", model)
    new_third_party = _new_third_party_modules(modules_before)

    assert field(response, "backend") == backend
    assert field(response, "model") == model
    assert field(response, "model_call_error") is None, (
        f"{model} failed: {field(response, 'model_call_error')!r}"
    )
    assert field(response, "text") is not None

    assert calls, f"{model} did not dispatch through urllib.request.urlopen"
    expected = urllib.parse.urlsplit(origin)
    for url in calls:
        parts = urllib.parse.urlsplit(url)
        assert (parts.scheme, parts.netloc) == (expected.scheme, expected.netloc), (
            f"{model} sent a request to {url!r}, not to its own adapter's {origin}"
        )
    assert any(path_fragment in url for url in calls), (
        f"{model}: no request matched {path_fragment!r} in {calls!r}"
    )

    assert _read_claude_calls(claude_log) == [], (
        f"{model} must not dispatch through the claude command"
    )
    assert new_third_party == [], (
        f"{model} pulled in non-standard-library modules: {new_third_party!r}"
    )