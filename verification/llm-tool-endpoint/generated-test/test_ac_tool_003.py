# hotdocs-criterion: sha256:6bb0261e6b24c72ee93f23e2d136d871cfe31d1da047e599332eb069ad817e27
import json
import urllib.request

import pytest

import llm_tool_endpoint


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


class _FakeReply:
    def __init__(self, document):
        self._bytes = json.dumps(document).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self, *args, **kwargs):
        return self._bytes


def _make_fake_urlopen(replies, recorded):
    queue = list(replies)

    def fake_urlopen(request, *args, **kwargs):
        if isinstance(request, str):
            url = request
            headers = {}
            data = kwargs.get("data") if "data" in kwargs else (args[0] if args else None)
        else:
            url = request.full_url
            headers = dict(request.header_items())
            data = request.data
        if isinstance(data, bytes):
            data = data.decode("utf-8")
        body = json.loads(data) if data else None
        recorded.append({"url": url, "headers": headers, "body": body})
        if not queue:
            raise AssertionError("more requests than scripted replies")
        return _FakeReply(queue.pop(0))

    return fake_urlopen


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


@pytest.fixture
def env(tmp_path, monkeypatch):
    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.chdir(work)
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "k")
    return work


def test_openai_tool_calls_then_stop(env, monkeypatch):
    recorded = []
    replies = [
        {
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
        },
        {
            "choices": [
                {
                    "message": {"role": "assistant", "content": "fin"},
                    "finish_reason": "stop",
                }
            ]
        },
    ]
    monkeypatch.setattr(urllib.request, "urlopen", _make_fake_urlopen(replies, recorded))

    calls = []

    def execute(name, arguments):
        calls.append((name, arguments))
        return ("contents", False)

    result = llm_tool_endpoint.run_tool_loop(
        "sys", "go", "openai:gpt-6-astra", TOOLS, execute
    )

    assert len(recorded) == 2

    first = recorded[0]
    assert first["url"] == "https://api.openai.com/v1/chat/completions"
    first_messages = first["body"]["messages"]
    assert first_messages[0] == {"role": "system", "content": "sys"}
    assert first_messages[1] == {"role": "user", "content": "go"}
    tool0 = first["body"]["tools"][0]
    assert tool0["type"] == "function"
    assert tool0["function"]["name"] == "read_file"

    assert calls == [("read_file", {"path": "x"})]

    second = recorded[1]
    assert second["body"]["messages"][-1] == {
        "role": "tool",
        "tool_call_id": "c1",
        "content": "contents",
    }

    assert field(result, "text") == "fin"
    assert field(result, "stop") == "end_turn"


def test_openai_length_is_truncated_and_runs_no_tools(env, monkeypatch):
    recorded = []
    replies = [
        {
            "choices": [
                {
                    "message": {"role": "assistant", "content": "partial"},
                    "finish_reason": "length",
                }
            ]
        },
        {
            "choices": [
                {
                    "message": {"role": "assistant", "content": "fin"},
                    "finish_reason": "stop",
                }
            ]
        },
    ]
    monkeypatch.setattr(urllib.request, "urlopen", _make_fake_urlopen(replies, recorded))

    calls = []

    def execute(name, arguments):
        calls.append((name, arguments))
        return ("contents", False)

    result = llm_tool_endpoint.run_tool_loop(
        "sys", "go", "openai:gpt-6-astra", TOOLS, execute
    )

    assert field(result, "stop") == "truncated"
    assert field(result, "text") == "partial"
    assert calls == []
    assert len(recorded) == 1