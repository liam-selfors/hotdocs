# hotdocs-criterion: sha256:a2d95de7c9bced90a07ce0f888ca51a4cbf64770d219a94590bc11e205f00cb2
import llm_endpoint


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def test_ac_endpoint_002_mock_backend_returns_hello(tmp_path, monkeypatch):
    # Isolate config discovery and the call log in a fresh directory.
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    monkeypatch.chdir(tmp_path)

    calls = []

    def mock_backend(prompt, model, **params):
        calls.append((prompt, model, dict(params)))
        return {
            "text": "hello",
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    prompt = "say something"
    result = llm_endpoint.complete(prompt, "claude-sonnet-5", backend=mock_backend)

    assert len(calls) == 1
    assert calls[0][0] == prompt

    assert field(result, "text") == "hello"
    assert field(result, "model") == "claude-sonnet-5"
    assert field(result, "model_call_error") is None