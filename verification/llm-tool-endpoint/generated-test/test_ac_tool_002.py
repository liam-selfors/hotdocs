import json
import urllib.request

import pytest

import llm_tool_endpoint


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


TOOLS = [
    {
        "name": "write_file",
        "description": "Write a file to disk.",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    }
]


class _FakeReply:
    def __init__(self, document):
        self._data = json.dumps(document).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self, *args, **kwargs):
        return self._data


def _install_fake_urlopen(monkeypatch, replies, recorded):
    script = list(replies)
    fallback = {"content": [{"type": "text", "text": "unexpected"}], "stop_reason": "end_turn"}

    def fake_urlopen(request, *args, **kwargs):
        url = request.full_url if hasattr(request, "full_url") else str(request)
        headers = {str(k).lower(): v for k, v in dict(request.header_items()).items()}
        data = request.data
        if isinstance(data, (bytes, bytearray)):
            data = data.decode("utf-8")
        body = json.loads(data) if data else None
        recorded.append({"url": url, "headers": headers, "body": body})
        document = script.pop(0) if script else fallback
        return _FakeReply(document)

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)


@pytest.fixture
def loop_env(tmp_path, monkeypatch):
    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.chdir(work)
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    return work


def _make_execute(calls):
    def execute(name, arguments):
        calls.append((name, json.loads(json.dumps(arguments))))
        return ("ok", False)

    return execute


def _system_text(system):
    if isinstance(system, str):
        return system
    assert isinstance(system, list) and system, system
    return "".join(block.get("text", "") for block in system if isinstance(block, dict))


def test_ac_tool_002_tool_use_then_end_turn(loop_env, monkeypatch):
    recorded = []
    calls = []
    replies = [
        {
            "content": [
                {"type": "text", "text": "writing"},
                {"type": "tool_use", "id": "t1", "name": "write_file", "input": {"path": "a.py"}},
            ],
            "stop_reason": "tool_use",
        },
        {"content": [{"type": "text", "text": "done"}], "stop_reason": "end_turn"},
    ]
    _install_fake_urlopen(monkeypatch, replies, recorded)

    result = llm_tool_endpoint.run_tool_loop(
        "sys", "go", "anthropic:claude-opus-5-5", TOOLS, _make_execute(calls)
    )

    # execute called exactly once with the tool_use block's name and input
    assert calls == [("write_file", {"path": "a.py"})]

    assert len(recorded) == 2

    first = recorded[0]
    assert first["url"] == "https://api.anthropic.com/v1/messages"
    body = first["body"]
    assert body["tool_choice"] == {"type": "auto"}
    assert "temperature" not in body
    assert _system_text(body["system"]) == "sys"
    assert body["messages"][0] == {"role": "user", "content": "go"}

    second_messages = recorded[1]["body"]["messages"]
    last = second_messages[-1]
    assert last["role"] == "user"
    assert last["content"] == [{"type": "tool_result", "tool_use_id": "t1", "content": "ok"}]

    assert field(result, "text") == "done"
    assert field(result, "turns") == 2
    assert field(result, "tool_calls") == 1
    assert field(result, "stop") == "end_turn"


def test_ac_tool_002_max_tokens_is_truncated(loop_env, monkeypatch):
    recorded = []
    calls = []
    replies = [
        {
            "content": [
                {"type": "text", "text": "writing"},
                {"type": "tool_use", "id": "t1", "name": "write_file", "input": {"path": "a.py"}},
            ],
            "stop_reason": "max_tokens",
        },
        {"content": [{"type": "text", "text": "done"}], "stop_reason": "end_turn"},
    ]
    _install_fake_urlopen(monkeypatch, replies, recorded)

    result = llm_tool_endpoint.run_tool_loop(
        "sys", "go", "anthropic:claude-opus-5-5", TOOLS, _make_execute(calls)
    )

    assert field(result, "stop") == "truncated"
    assert field(result, "turns") == 1
    assert calls == []
    assert len(recorded) == 1