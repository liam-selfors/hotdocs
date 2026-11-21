# hotdocs-criterion: sha256:dde5479585be31a6bf8df5ab9d0eaf7a19425e89dd8cb291dab5061f11f1f2cd
import json

import llm_endpoint


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def test_ac_endpoint_002_injected_mock_backend_returns_hello(tmp_path, monkeypatch):
    # Isolate config discovery and the call log in a fresh directory.
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.chdir(work)

    log_path = tmp_path / "mock_calls.log"

    def mock_anthropic_backend(prompt, model, **params):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"prompt": prompt, "model": model}) + "\n")
        return {
            "text": "hello",
            "model": model,
            "backend": "mock-anthropic",
            "model_call_error": None,
        }

    prompt = "Say something, please."
    response = llm_endpoint.complete(
        prompt, model="claude-sonnet-5", backend=mock_anthropic_backend
    )

    assert field(response, "text") == "hello"
    assert field(response, "model") == "claude-sonnet-5"
    assert field(response, "model_call_error") is None

    # The injected backend was actually used, exactly once, with the prompt.
    assert log_path.is_file()
    lines = [line for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(lines) == 1
    assert json.loads(lines[0])["prompt"] == prompt