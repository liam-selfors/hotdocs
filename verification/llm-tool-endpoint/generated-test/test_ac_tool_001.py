"""AC-TOOL-001 (Covers: R-TOOL-001).

Given urllib.request.urlopen replaced by a function that records calls,
run_tool_loop over a `gemini` or `ollama` model raises ToolUseUnsupported
with no request recorded; over `anthropic` with no ANTHROPIC_API_KEY it
returns stop "error", model_call_error category "auth", turns 0, and no
request recorded.
"""

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


@pytest.fixture
def recorded_requests(monkeypatch, tmp_path):
    # Loop-test fixture: no repo_root, no VAR_HOTDOCS_CONFIG, fresh empty cwd.
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    workdir = tmp_path / "cwd"
    workdir.mkdir()
    monkeypatch.chdir(workdir)

    calls = []

    def fake_urlopen(request, *args, **kwargs):
        url = getattr(request, "full_url", request)
        headers = dict(getattr(request, "header_items", lambda: [])())
        data = getattr(request, "data", None)
        body = None
        if data:
            try:
                body = json.loads(data.decode("utf-8"))
            except Exception:
                body = data
        calls.append({"url": url, "headers": headers, "body": body})
        # A harmless terminal reply so a misbehaving loop does not spin.
        return _Reply(
            {
                "content": [{"type": "text", "text": "x"}],
                "stop_reason": "end_turn",
                "choices": [
                    {
                        "message": {"role": "assistant", "content": "x"},
                        "finish_reason": "stop",
                    }
                ],
            }
        )

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    return calls


def _make_execute():
    executed = []

    def execute(name, arguments):
        executed.append((name, arguments))
        return ("", False)

    return execute, executed


@pytest.mark.parametrize("model", ["gemini:g", "ollama:llama3.2"])
def test_gemini_and_ollama_raise_tool_use_unsupported_without_request(
    recorded_requests, model
):
    execute, executed = _make_execute()

    with pytest.raises(llm_tool_endpoint.ToolUseUnsupported):
        llm_tool_endpoint.run_tool_loop("s", "p", model, [], execute)

    assert recorded_requests == []
    assert executed == []


def test_anthropic_without_key_returns_auth_error_without_request(
    recorded_requests, monkeypatch
):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    execute, executed = _make_execute()

    result = llm_tool_endpoint.run_tool_loop(
        "s", "p", "anthropic:claude-opus-5-5", [], execute
    )

    assert field(result, "stop") == "error"
    error = field(result, "model_call_error")
    assert error is not None
    assert field(error, "category") == "auth"
    assert field(result, "turns") == 0
    assert recorded_requests == []
    assert executed == []