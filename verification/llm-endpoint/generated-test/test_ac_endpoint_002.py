# hotdocs-criterion: sha256:9a04a661706987459dcee6c360b1eaffaddbffb0f5a7f296d402ba9ef34aa6a2
import llm_endpoint


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def test_ac_endpoint_002_mock_anthropic_backend_returns_hello(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    monkeypatch.chdir(tmp_path)

    calls = []

    def mock_anthropic_backend(prompt, model, **params):
        calls.append((prompt, model, dict(params)))
        return {
            "text": "hello",
            "model": model,
            "backend": "anthropic",
            "model_call_error": None,
        }

    prompt = "Say something, please."
    response = llm_endpoint.complete(
        prompt, model="claude-sonnet-5", backend=mock_anthropic_backend
    )

    assert len(calls) == 1
    assert calls[0][0] == prompt

    assert field(response, "text") == "hello"
    assert field(response, "model") == "claude-sonnet-5"
    assert field(response, "model_call_error") is None