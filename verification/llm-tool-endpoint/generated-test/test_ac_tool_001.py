# hotdocs-criterion: sha256:409bb3eb01847d4701cd5b7d27430250f9041900fc2b54af2c60c7e5cbe333a8
import urllib.request

import pytest

import llm_tool_endpoint


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    work = tmp_path / "work"
    work.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.chdir(work)
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)

    recorded = []

    def fake_urlopen(request, timeout=None, *args, **kwargs):
        recorded.append(
            {
                "url": getattr(request, "full_url", request),
                "headers": dict(getattr(request, "headers", {}) or {}),
            }
        )
        raise AssertionError("no HTTP request may be made")

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    return recorded


def _make_execute(calls):
    def execute(name, arguments):
        calls.append((name, arguments))
        return ("ok", False)

    return execute


@pytest.mark.parametrize(
    "model, provider",
    [("gemini:g", "gemini"), ("ollama:llama3.2", "ollama")],
)
def test_unsupported_providers_raise_before_any_request(isolated, model, provider):
    recorded = isolated
    calls = []
    execute = _make_execute(calls)

    with pytest.raises(llm_tool_endpoint.ToolUseUnsupported) as excinfo:
        llm_tool_endpoint.run_tool_loop("s", "p", model, [], execute)

    assert provider in str(excinfo.value)
    assert recorded == []
    assert calls == []


def test_anthropic_without_key_returns_auth_error_without_request(isolated, monkeypatch):
    recorded = isolated
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    calls = []
    execute = _make_execute(calls)

    result = llm_tool_endpoint.run_tool_loop(
        "s", "p", "anthropic:claude-opus-5-5", [], execute
    )

    assert field(result, "stop") == "error"
    error = field(result, "model_call_error")
    assert error is not None
    assert field(error, "category") == "auth"
    assert field(result, "turns") == 0
    assert recorded == []
    assert calls == []