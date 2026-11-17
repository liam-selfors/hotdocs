import json

import llm_endpoint


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def test_ac_endpoint_002_mock_backend_returns_hello(tmp_path, monkeypatch):
    # Isolate config discovery and the call log from the real environment.
    workdir = tmp_path / "work"
    workdir.mkdir()
    monkeypatch.chdir(workdir)
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)

    invocation_log = tmp_path / "backend_invocations.jsonl"

    def mock_backend(prompt, model, **params):
        with open(invocation_log, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"prompt": prompt, "model": model}) + "\n")
        return {
            "text": "hello",
            "model": model,
            "backend": "mock-anthropic",
            "model_call_error": None,
        }

    prompt = "Say something, please."
    response = llm_endpoint.complete(
        prompt, model="claude-sonnet-5", backend=mock_backend
    )

    # The injected backend was actually used.
    assert invocation_log.exists()
    records = [
        json.loads(line)
        for line in invocation_log.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(records) == 1
    assert records[0]["prompt"] == prompt

    # Then clause.
    assert field(response, "text") == "hello"
    assert field(response, "model") == "claude-sonnet-5"
    assert field(response, "model_call_error") is None