# hotdocs-criterion: sha256:b0d5da4aaf3263606ad8fef446a98162a78326805b12274fa22b7c6c41daeb8e
import urllib.request

import pytest

import llm_tool_endpoint


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


@pytest.fixture
def recorded(monkeypatch, tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.chdir(work)
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)

    calls = []

    def fake_urlopen(request, *args, **kwargs):
        calls.append(request)
        raise AssertionError("no HTTP request may be made")

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    return calls


def _execute(name, arguments):
    return ("ok", False)


@pytest.mark.parametrize("model", ["gemini:g", "ollama:llama3.2"])
def test_unsupported_providers_raise_before_any_request(recorded, model):
    with pytest.raises(llm_tool_endpoint.ToolUseUnsupported):
        llm_tool_endpoint.run_tool_loop("s", "p", model, [], _execute)
    assert recorded == []


def test_both_unsupported_providers_raise_and_record_nothing(recorded):
    for model in ("gemini:g", "ollama:llama3.2"):
        with pytest.raises(llm_tool_endpoint.ToolUseUnsupported):
            llm_tool_endpoint.run_tool_loop("s", "p", model, [], _execute)
    assert recorded == []


def test_anthropic_without_key_returns_auth_error_without_request(recorded, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    result = llm_tool_endpoint.run_tool_loop(
        "s", "p", "anthropic:claude-opus-5-5", [], _execute
    )

    assert field(result, "stop") == "error"
    error = field(result, "model_call_error")
    assert error is not None
    assert field(error, "category") == "auth"
    assert field(result, "turns") == 0
    assert recorded == []