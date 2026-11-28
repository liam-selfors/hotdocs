# hotdocs-criterion: sha256:d2465aa9d22e3231cb10ee5fc734a8b5a90014b61d42f7891885973f65fc2905
import json
import urllib.request

import llm_tool_endpoint


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


class _FakeReply:
    def __init__(self, document):
        self._data = json.dumps(document).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self, *args, **kwargs):
        return self._data


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


def _install(monkeypatch, tmp_path, replies):
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "k")
    workdir = tmp_path / "work"
    workdir.mkdir()
    monkeypatch.chdir(workdir)

    recorded = []
    remaining = list(replies)

    def fake_urlopen(request, timeout=None, *args, **kwargs):
        url = getattr(request, "full_url", request)
        data = getattr(request, "data", None)
        if isinstance(data, (bytes, bytearray)):
            body = json.loads(data.decode("utf-8"))
        elif isinstance(data, str):
            body = json.loads(data)
        else:
            body = None
        headers = {}
        if hasattr(request, "header_items"):
            headers = {k.lower(): v for k, v in request.header_items()}
        recorded.append({"url": url, "headers": headers, "body": body})
        assert remaining, "more requests made than scripted replies"
        return _FakeReply(remaining.pop(0))

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    return recorded


def _make_execute():
    calls = []

    def execute(name, arguments):
        calls.append((name, arguments))
        return ("contents", False)

    return execute, calls


def test_ac_tool_003_tool_calls_then_stop(monkeypatch, tmp_path):
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
    recorded = _install(monkeypatch, tmp_path, [first, second])
    execute, calls = _make_execute()

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


def test_ac_tool_003_length_is_truncated(monkeypatch, tmp_path):
    first = {
        "choices": [
            {
                "message": {"role": "assistant", "content": "partial"},
                "finish_reason": "length",
            }
        ]
    }
    recorded = _install(monkeypatch, tmp_path, [first])
    execute, calls = _make_execute()

    result = llm_tool_endpoint.run_tool_loop(
        "sys", "go", "openai:gpt-6-astra", TOOLS, execute
    )

    assert len(recorded) == 1
    assert field(result, "stop") == "truncated"
    assert field(result, "text") == "partial"
    assert calls == []