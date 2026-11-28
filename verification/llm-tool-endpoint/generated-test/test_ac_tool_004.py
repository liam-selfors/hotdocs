# hotdocs-criterion: sha256:30a6a52d97a7041f0667bdfc1323b39f3c43d573ece4535aac6fc51a02743473
import json
import urllib.request

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


def _decode_body(request):
    data = request.data
    if data is None:
        return None
    if isinstance(data, (bytes, bytearray)):
        data = data.decode("utf-8")
    return json.loads(data)


def test_ac_tool_004(monkeypatch, tmp_path):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    monkeypatch.chdir(tmp_path)

    first_reply = {
        "id": "msg_1",
        "type": "message",
        "role": "assistant",
        "model": "claude-opus-5-5",
        "content": [
            {"type": "tool_use", "id": "a", "name": "boom", "input": {}},
            {"type": "tool_use", "id": "b", "name": "nope", "input": {}},
            {"type": "tool_use", "id": "c", "name": "boom", "input": "text"},
        ],
        "stop_reason": "tool_use",
        "stop_sequence": None,
        "usage": {"input_tokens": 1, "output_tokens": 1},
    }
    second_reply = {
        "id": "msg_2",
        "type": "message",
        "role": "assistant",
        "model": "claude-opus-5-5",
        "content": [{"type": "text", "text": "done"}],
        "stop_reason": "end_turn",
        "stop_sequence": None,
        "usage": {"input_tokens": 1, "output_tokens": 1},
    }
    scripted = [first_reply, second_reply]
    recorded = []

    def fake_urlopen(request, *args, **kwargs):
        recorded.append(
            {
                "url": request.full_url,
                "headers": {k.lower(): v for k, v in request.header_items()},
                "body": _decode_body(request),
            }
        )
        if len(recorded) > len(scripted):
            raise AssertionError("more requests than scripted replies")
        return _Reply(scripted[len(recorded) - 1])

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    tools = [
        {
            "name": "boom",
            "description": "explodes",
            "input_schema": {"type": "object", "properties": {}},
        }
    ]
    calls = []

    def execute(name, arguments):
        calls.append((name, arguments))
        raise ValueError("bad")

    result = llm_tool_endpoint.run_tool_loop(
        "sys", "go", "anthropic:claude-opus-5-5", tools, execute
    )

    # execute was called exactly once, for the valid "boom" call
    assert len(calls) == 1
    assert calls[0][0] == "boom"
    assert calls[0][1] == {}

    assert len(recorded) == 2
    second_body = recorded[1]["body"]
    messages = second_body["messages"]
    last = messages[-1]
    assert last["role"] == "user"
    results = last["content"]
    assert isinstance(results, list)
    assert len(results) == 3

    expected = [
        ("a", "tool error: ValueError: bad"),
        ("b", "unknown tool: nope"),
        ("c", "arguments must be a JSON object"),
    ]
    for block, (tool_use_id, text) in zip(results, expected):
        assert block["type"] == "tool_result"
        assert block["tool_use_id"] == tool_use_id
        content = block["content"]
        if isinstance(content, list):
            content = "".join(
                part.get("text", "") for part in content if isinstance(part, dict)
            )
        assert content == text
        assert block.get("is_error") is True

    assert field(result, "stop") == "end_turn"