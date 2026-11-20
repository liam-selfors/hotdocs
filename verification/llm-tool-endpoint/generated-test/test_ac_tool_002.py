# hotdocs-criterion: sha256:3dc58e5733862569b637a62e644815a3802896dc549a601ebf77657b431b7b12
import json
import urllib.request

import pytest

import llm_tool_endpoint


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


class _Reply:
    def __init__(self, doc):
        self._data = json.dumps(doc).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self, *args, **kwargs):
        return self._data


FIRST_TOOL_USE = {
    "content": [
        {"type": "text", "text": "writing"},
        {"type": "tool_use", "id": "t1", "name": "write_file",
         "input": {"path": "a.py"}},
    ],
    "stop_reason": "tool_use",
}

SECOND_END = {
    "content": [{"type": "text", "text": "done"}],
    "stop_reason": "end_turn",
}

FIRST_MAX_TOKENS = {
    "content": [
        {"type": "text", "text": "writing"},
        {"type": "tool_use", "id": "t1", "name": "write_file",
         "input": {"path": "a.py"}},
    ],
    "stop_reason": "max_tokens",
}

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


@pytest.fixture
def env(tmp_path, monkeypatch):
    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.chdir(work)
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    return work


def _install_urlopen(monkeypatch, replies):
    requests = []
    queue = list(replies)

    def fake_urlopen(request, *args, **kwargs):
        url = getattr(request, "full_url", None) or request.get_full_url()
        headers = {k.lower(): v for k, v in request.header_items()}
        data = request.data
        if isinstance(data, (bytes, bytearray)):
            body = json.loads(data.decode("utf-8"))
        else:
            body = json.loads(data)
        requests.append({"url": url, "headers": headers, "body": body})
        assert queue, "more requests than scripted replies"
        return _Reply(queue.pop(0))

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    return requests


def _make_execute():
    calls = []

    def execute(*args, **kwargs):
        calls.append((args, kwargs))
        return ("ok", False)

    return execute, calls


def _system_text(system):
    if isinstance(system, str):
        return system
    return "".join(
        block.get("text", "") for block in system if isinstance(block, dict)
    )


def test_tool_use_then_end_turn(env, monkeypatch):
    requests = _install_urlopen(monkeypatch, [FIRST_TOOL_USE, SECOND_END])
    execute, calls = _make_execute()

    result = llm_tool_endpoint.run_tool_loop(
        "sys", "go", "anthropic:claude-opus-5-5", TOOLS, execute
    )

    assert len(calls) == 1
    args, kwargs = calls[0]
    assert kwargs == {}
    assert args == ("write_file", {"path": "a.py"})

    assert len(requests) == 2
    first = requests[0]
    assert first["url"] == "https://api.anthropic.com/v1/messages"
    assert first["body"]["tool_choice"] == {"type": "auto"}
    assert "temperature" not in first["body"]
    assert _system_text(first["body"]["system"]) == "sys"
    assert first["body"]["messages"] == [{"role": "user", "content": "go"}]

    second = requests[1]
    last = second["body"]["messages"][-1]
    assert last["role"] == "user"
    assert last["content"] == [
        {"type": "tool_result", "tool_use_id": "t1", "content": "ok"}
    ]

    assert field(result, "text") == "done"
    assert field(result, "turns") == 2
    assert field(result, "tool_calls") == 1
    assert field(result, "stop") == "end_turn"


def test_max_tokens_truncates_without_running_tools(env, monkeypatch):
    requests = _install_urlopen(monkeypatch, [FIRST_MAX_TOKENS, SECOND_END])
    execute, calls = _make_execute()

    result = llm_tool_endpoint.run_tool_loop(
        "sys", "go", "anthropic:claude-opus-5-5", TOOLS, execute
    )

    assert field(result, "stop") == "truncated"
    assert field(result, "turns") == 1
    assert calls == []
    assert len(requests) == 1