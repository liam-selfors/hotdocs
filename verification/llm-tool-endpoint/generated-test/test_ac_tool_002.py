# hotdocs-criterion: sha256:a9a6c8037766f42a201a4a9aadfc2654482da3c3de2b607ff5116afed6de5c81
import json
import urllib.request

import pytest

import llm_tool_endpoint


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


TOOLS = [
    {
        "name": "write_file",
        "description": "Write a file.",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    }
]


class _Reply:
    def __init__(self, doc):
        self._data = json.dumps(doc).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self, *args, **kwargs):
        return self._data


def _install(monkeypatch, tmp_path, replies):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    workdir = tmp_path / "cwd"
    workdir.mkdir()
    monkeypatch.chdir(workdir)

    requests = []
    queue = list(replies)

    def fake_urlopen(request, timeout=None, *args, **kwargs):
        url = request.full_url if hasattr(request, "full_url") else str(request)
        data = request.data
        if isinstance(data, (bytes, bytearray)):
            data = data.decode("utf-8")
        body = json.loads(data) if data else None
        headers = {k.lower(): v for k, v in request.header_items()}
        requests.append({"url": url, "headers": headers, "body": body})
        if not queue:
            raise AssertionError("unexpected extra request")
        return _Reply(queue.pop(0))

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    return requests


def _system_text(system):
    if isinstance(system, str):
        return system
    return "".join(
        block.get("text", "")
        for block in system
        if isinstance(block, dict) and block.get("type") == "text"
    )


FIRST_TOOL_USE = {
    "content": [
        {"type": "text", "text": "writing"},
        {"type": "tool_use", "id": "t1", "name": "write_file", "input": {"path": "a.py"}},
    ],
    "stop_reason": "tool_use",
}

SECOND_END = {"content": [{"type": "text", "text": "done"}], "stop_reason": "end_turn"}


def test_tool_use_then_end_turn(monkeypatch, tmp_path):
    requests = _install(monkeypatch, tmp_path, [FIRST_TOOL_USE, SECOND_END])
    calls = []

    def execute(*args, **kwargs):
        calls.append((args, kwargs))
        return ("ok", False)

    result = llm_tool_endpoint.run_tool_loop(
        "sys", "go", "anthropic:claude-opus-5-5", TOOLS, execute
    )

    assert calls == [(("write_file", {"path": "a.py"}), {})]

    assert len(requests) == 2
    first = requests[0]
    assert first["url"] == "https://api.anthropic.com/v1/messages"
    body = first["body"]
    assert body["tool_choice"] == {"type": "auto"}
    assert "temperature" not in body
    assert _system_text(body["system"]) == "sys"
    assert body["messages"] == [{"role": "user", "content": "go"}]

    second_body = requests[1]["body"]
    assert requests[1]["url"] == "https://api.anthropic.com/v1/messages"
    last = second_body["messages"][-1]
    assert last == {
        "role": "user",
        "content": [{"type": "tool_result", "tool_use_id": "t1", "content": "ok"}],
    }

    assert field(result, "text") == "done"
    assert field(result, "turns") == 2
    assert field(result, "tool_calls") == 1
    assert field(result, "stop") == "end_turn"


def test_max_tokens_truncates_without_running_tools(monkeypatch, tmp_path):
    first = dict(FIRST_TOOL_USE)
    first["stop_reason"] = "max_tokens"
    requests = _install(monkeypatch, tmp_path, [first, SECOND_END])
    calls = []

    def execute(*args, **kwargs):
        calls.append((args, kwargs))
        return ("ok", False)

    result = llm_tool_endpoint.run_tool_loop(
        "sys", "go", "anthropic:claude-opus-5-5", TOOLS, execute
    )

    assert calls == []
    assert len(requests) == 1
    assert field(result, "stop") == "truncated"
    assert field(result, "turns") == 1