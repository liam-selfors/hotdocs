import json
import os

import pytest

import llm_endpoint


def _field(value, name):
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


@pytest.fixture
def isolated_cwd(tmp_path, monkeypatch):
    workdir = tmp_path / "work"
    workdir.mkdir()
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    monkeypatch.chdir(workdir)
    return tmp_path


def test_ac_endpoint_002_mock_anthropic_backend_returns_hello(isolated_cwd):
    invocation_log = isolated_cwd / "mock_invocations.jsonl"

    def mock_anthropic_backend(prompt, model, **params):
        with open(invocation_log, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"prompt": prompt, "model": model}) + "\n")
        return {
            "text": "hello",
            "model": model,
            "backend": "anthropic",
            "model_call_error": None,
        }

    prompt = "Say something, please."
    result = llm_endpoint.complete(
        prompt, "claude-sonnet-5", backend=mock_anthropic_backend
    )

    assert result is not None
    assert _field(result, "text") == "hello"
    assert _field(result, "model") == "claude-sonnet-5"
    assert _field(result, "model_call_error") is None

    # The injected mock was actually invoked with the caller's prompt.
    assert invocation_log.exists(), "injected backend was never called"
    records = [
        json.loads(line)
        for line in invocation_log.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(records) >= 1
    assert records[0]["prompt"] == prompt


def test_ac_endpoint_002_any_prompt_yields_hello(isolated_cwd):
    def mock_anthropic_backend(prompt, model, **params):
        return {
            "text": "hello",
            "model": model,
            "backend": "anthropic",
            "model_call_error": None,
        }

    for prompt in ["", "another prompt", "multi\nline\nprompt"]:
        result = llm_endpoint.complete(
            prompt, "claude-sonnet-5", backend=mock_anthropic_backend
        )
        assert _field(result, "text") == "hello"
        assert _field(result, "model") == "claude-sonnet-5"
        assert _field(result, "model_call_error") is None