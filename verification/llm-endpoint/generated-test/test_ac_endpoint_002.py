import json

import pytest

import llm_endpoint


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _make_mock_anthropic_backend(log_path):
    """A mock Anthropic backend returning "hello" for any prompt.

    Matches the documented injected-backend shape:
    backend(prompt, model, **params) -> ModelResponse
    """

    def backend(prompt, model, **params):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(
                json.dumps(
                    {
                        "prompt": prompt,
                        "model": model,
                        "params": sorted(params.keys()),
                    }
                )
                + "\n"
            )
        return {
            "text": "hello",
            "model": model,
            "backend": "anthropic",
            "model_call_error": None,
        }

    return backend


@pytest.mark.parametrize(
    "prompt",
    ["Say hi.", "Write a haiku about the sea.", ""],
)
def test_ac_endpoint_002_complete_returns_mock_text_and_model(
    tmp_path, monkeypatch, prompt
):
    # Isolate config discovery and the call log to a fresh directory.
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    workdir = tmp_path / "work"
    workdir.mkdir()
    monkeypatch.chdir(workdir)

    log_path = tmp_path / "backend_invocations.jsonl"
    backend = _make_mock_anthropic_backend(log_path)

    response = llm_endpoint.complete(
        prompt, model="claude-sonnet-5", backend=backend
    )

    # The injected mock was actually used.
    assert log_path.exists(), "injected backend was never invoked"
    records = [
        json.loads(line)
        for line in log_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(records) >= 1

    # Then clause: text "hello", model "claude-sonnet-5", model_call_error null.
    assert field(response, "text") == "hello"
    assert field(response, "model") == "claude-sonnet-5"
    assert field(response, "model_call_error") is None