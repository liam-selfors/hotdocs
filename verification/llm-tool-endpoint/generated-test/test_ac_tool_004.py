# hotdocs-criterion: sha256:c517311ad00dc04fb9063c273cffd794e0517e43a22411af6c6e783cbb2c4da5
import json
import urllib.request

import pytest

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


@pytest.fixture
def loop_env(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.chdir(work)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    return work


def test_ac_tool_004_error_results_returned_and_loop_continues(loop_env, monkeypatch):
    replies = [
        {
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
        },
        {
            "id": "msg_2",
            "type": "message",
            "role": "assistant",
            "model": "claude-opus-5-5",
            "content": [{"type": "text", "text": "done"}],
            "stop_reason": "end_turn",
        },
    ]
    requests = []

    def fake_urlopen(request, *args, **kwargs):
        body = request.data
        if isinstance(body, bytes):
            body = body.decode("utf-8")
        requests.append(
            {
                "url": request.full_url,
                "headers": dict(request.header_items()),
                "body": json.loads(body) if body else None,
            }
        )
        index = len(requests) - 1
        assert index < len(replies), "more requests than scripted replies"
        return _FakeReply(replies[index])

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

    assert calls == [("boom", {})]
    assert len(requests) == 2

    second_messages = requests[1]["body"]["messages"]
    last = second_messages[-1]
    assert last["role"] == "user"
    results = last["content"]
    assert isinstance(results, list)
    assert len(results) == 3
    for item in results:
        assert item["type"] == "tool_result"
    assert [r["tool_use_id"] for r in results] == ["a", "b", "c"]
    assert [r["content"] for r in results] == [
        "tool error: ValueError: bad",
        "unknown tool: nope",
        "arguments must be a JSON object",
    ]
    for item in results:
        assert item.get("is_error") is True

    assert field(result, "stop") == "end_turn"