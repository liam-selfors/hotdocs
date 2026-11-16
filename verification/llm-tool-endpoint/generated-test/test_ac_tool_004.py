import json
import urllib.request

import pytest

import llm_tool_endpoint


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


class _FakeReply:
    def __init__(self, document):
        self._payload = json.dumps(document).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self, *args, **kwargs):
        return self._payload


def _decode_body(request):
    data = request.data
    if data is None:
        return None
    if isinstance(data, (bytes, bytearray)):
        data = data.decode("utf-8")
    return json.loads(data)


def _result_text(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            block.get("text", "")
            for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        )
    return content


def test_ac_tool_004_error_results_returned_and_loop_continues(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.chdir(work)

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
        "usage": {"input_tokens": 10, "output_tokens": 10},
    }
    second_reply = {
        "id": "msg_2",
        "type": "message",
        "role": "assistant",
        "model": "claude-opus-5-5",
        "content": [{"type": "text", "text": "finished"}],
        "stop_reason": "end_turn",
        "stop_sequence": None,
        "usage": {"input_tokens": 10, "output_tokens": 10},
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
        index = len(recorded) - 1
        document = scripted[index] if index < len(scripted) else second_reply
        return _FakeReply(document)

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    tools = [
        {
            "name": "boom",
            "description": "Always fails.",
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

    # execute was called exactly once, for the valid "boom" call.
    assert len(calls) == 1
    assert calls[0][0] == "boom"
    assert calls[0][1] == {}

    # Exactly two model requests: the loop continued after the errors.
    assert len(recorded) == 2

    second_body = recorded[1]["body"]
    assert isinstance(second_body, dict)
    messages = second_body["messages"]
    last = messages[-1]
    assert last["role"] == "user"
    results = [
        block
        for block in last["content"]
        if isinstance(block, dict) and block.get("type") == "tool_result"
    ]
    assert len(results) == 3

    expected = [
        ("a", "tool error: ValueError: bad"),
        ("b", "unknown tool: nope"),
        ("c", "arguments must be a JSON object"),
    ]
    for block, (tool_use_id, text) in zip(results, expected):
        assert block["tool_use_id"] == tool_use_id
        assert _result_text(block["content"]) == text
        assert block.get("is_error") is True

    assert field(result, "stop") == "end_turn"