import json
import urllib.request

import pytest

import llm_tool_endpoint


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


TOOLS = [
    {
        "name": "read_file",
        "description": "Read a file from the workspace.",
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

    def close(self):
        pass


def _install_fake_urlopen(monkeypatch, replies):
    recorded = []
    queue = list(replies)

    def fake_urlopen(request, *args, **kwargs):
        if isinstance(request, str):
            url = request
            headers = {}
            body = None
        else:
            url = request.full_url
            headers = {k.lower(): v for k, v in request.header_items()}
            data = request.data
            if isinstance(data, (bytes, bytearray)):
                data = data.decode("utf-8")
            body = json.loads(data) if data else None
        recorded.append({"url": url, "headers": headers, "body": body})
        if not queue:
            raise AssertionError("more requests sent than scripted replies")
        return _FakeReply(queue.pop(0))

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    return recorded


@pytest.fixture
def loop_env(monkeypatch, tmp_path):
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "k")
    workdir = tmp_path / "work"
    workdir.mkdir()
    monkeypatch.chdir(workdir)
    return monkeypatch


def _make_execute(calls):
    def execute(name, arguments):
        calls.append((name, arguments))
        return ("contents", False)

    return execute


def test_openai_tool_call_round_trip(loop_env):
    first = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "c1",
                            "type": "function",
                            "function": {
                                "name": "read_file",
                                "arguments": "{\"path\": \"x\"}",
                            },
                        }
                    ],
                },
                "finish_reason": "tool_calls",
            }
        ]
    }
    second = {
        "choices": [
            {
                "message": {"role": "assistant", "content": "fin"},
                "finish_reason": "stop",
            }
        ]
    }
    recorded = _install_fake_urlopen(loop_env, [first, second])
    calls = []
    execute = _make_execute(calls)

    result = llm_tool_endpoint.run_tool_loop(
        "sys", "go", "openai:gpt-6-astra", TOOLS, execute
    )

    assert len(recorded) == 2

    req1 = recorded[0]
    assert req1["url"] == "https://api.openai.com/v1/chat/completions"
    body1 = req1["body"]
    assert body1 is not None
    messages1 = body1["messages"]
    assert messages1[0] == {"role": "system", "content": "sys"}
    assert messages1[1] == {"role": "user", "content": "go"}
    tool0 = body1["tools"][0]
    assert tool0["type"] == "function"
    assert tool0["function"]["name"] == "read_file"

    assert calls == [("read_file", {"path": "x"})]

    body2 = recorded[1]["body"]
    assert body2 is not None
    assert body2["messages"][-1] == {
        "role": "tool",
        "tool_call_id": "c1",
        "content": "contents",
    }

    assert field(result, "text") == "fin"
    assert field(result, "stop") == "end_turn"


def test_openai_length_finish_is_truncated_without_tools(loop_env):
    first = {
        "choices": [
            {
                "message": {"role": "assistant", "content": "partial"},
                "finish_reason": "length",
            }
        ]
    }
    recorded = _install_fake_urlopen(loop_env, [first])
    calls = []
    execute = _make_execute(calls)

    result = llm_tool_endpoint.run_tool_loop(
        "sys", "go", "openai:gpt-6-astra", TOOLS, execute
    )

    assert len(recorded) == 1
    assert field(result, "stop") == "truncated"
    assert field(result, "text") == "partial"
    assert calls == []