# hotdocs-criterion: sha256:e3f8762228df5bf19e036f8d3c36785f6cd308b1c1315cdf1248723b097a3b5f
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
    def __init__(self, payload):
        self._data = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self, *args, **kwargs):
        return self._data


@pytest.fixture
def setup(monkeypatch, tmp_path):
    workdir = tmp_path / "work"
    workdir.mkdir()
    monkeypatch.chdir(workdir)
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")

    requests = []

    def fake_urlopen(request, *args, **kwargs):
        data = request.data
        if isinstance(data, bytes):
            data = data.decode("utf-8")
        body = json.loads(data) if data else None
        requests.append(
            {
                "url": request.full_url,
                "headers": dict(request.header_items()),
                "body": body,
                "timeout": kwargs.get("timeout"),
            }
        )
        return _FakeResponse(REPLY)

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    calls = []

    def execute(name, arguments):
        calls.append((name, arguments))
        return ("ok", False)

    return requests, calls, execute


def test_max_turns_budget(setup):
    requests, calls, execute = setup
    result = llm_tool_endpoint.run_tool_loop(
        "sys", "go", MODEL, TOOLS, execute, max_turns=3
    )
    assert len(requests) == 3
    assert field(result, "turns") == 3
    assert field(result, "tool_calls") == 3
    assert field(result, "stop") == "budget_exhausted"


def test_max_tool_calls_budget(setup):
    requests, calls, execute = setup
    result = llm_tool_endpoint.run_tool_loop(
        "sys", "go", MODEL, TOOLS, execute, max_turns=10, max_tool_calls=2
    )
    assert len(calls) == 2
    assert field(result, "tool_calls") == 2
    assert field(result, "stop") == "budget_exhausted"


def test_wall_seconds_zero(setup):
    requests, calls, execute = setup
    result = llm_tool_endpoint.run_tool_loop(
        "sys", "go", MODEL, TOOLS, execute, wall_seconds=0
    )
    assert len(requests) == 0
    assert field(result, "stop") == "budget_exhausted"