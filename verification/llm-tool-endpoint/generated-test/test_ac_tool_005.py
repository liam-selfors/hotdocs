import json
import urllib.request

import pytest

import llm_tool_endpoint


MODEL = "anthropic:claude-opus-5-5"

TOOLS = [{"name": "t", "description": "d", "input_schema": {"type": "object"}}]

REPLY = {
    "content": [{"type": "tool_use", "id": "u1", "name": "t", "input": {}}],
    "stop_reason": "tool_use",
}


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


class _FakeResponse:
    def __init__(self, document):
        self._payload = json.dumps(document).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self, *args, **kwargs):
        return self._payload

    def close(self):
        pass


@pytest.fixture
def setup(monkeypatch, tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.chdir(work)
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")

    recorded = []

    def fake_urlopen(request, *args, **kwargs):
        data = request.data
        if isinstance(data, (bytes, bytearray)):
            body = json.loads(data.decode("utf-8"))
        elif isinstance(data, str):
            body = json.loads(data)
        else:
            body = None
        recorded.append(
            {
                "url": request.full_url,
                "headers": {k.lower(): v for k, v in request.header_items()},
                "body": body,
                "timeout": kwargs.get("timeout", args[1] if len(args) > 1 else None),
            }
        )
        return _FakeResponse(REPLY)

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    executed = []

    def execute(name, arguments):
        executed.append((name, arguments))
        return ("ok", False)

    return recorded, executed, execute


def test_max_turns_budget_exhausted(setup):
    recorded, executed, execute = setup

    result = llm_tool_endpoint.run_tool_loop(
        "sys", "go", MODEL, TOOLS, execute, max_turns=3
    )

    assert len(recorded) == 3
    assert field(result, "turns") == 3
    assert field(result, "tool_calls") == 3
    assert field(result, "stop") == "budget_exhausted"


def test_max_tool_calls_budget_exhausted(setup):
    recorded, executed, execute = setup

    result = llm_tool_endpoint.run_tool_loop(
        "sys", "go", MODEL, TOOLS, execute, max_turns=10, max_tool_calls=2
    )

    assert len(executed) == 2
    assert field(result, "tool_calls") == 2
    assert field(result, "stop") == "budget_exhausted"


def test_zero_wall_seconds_budget_exhausted(setup):
    recorded, executed, execute = setup

    result = llm_tool_endpoint.run_tool_loop(
        "sys", "go", MODEL, TOOLS, execute, wall_seconds=0
    )

    assert recorded == []
    assert field(result, "stop") == "budget_exhausted"