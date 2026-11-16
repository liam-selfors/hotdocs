import io
import json
import urllib.error

import pytest

import llm_endpoint


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


@pytest.fixture
def isolated_cwd(tmp_path, monkeypatch):
    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    monkeypatch.chdir(work)
    return work


def _make_rate_limited_backend(log_path):
    def backend(prompt, model, **params):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"prompt": prompt, "model": model}) + "\n")
        raise urllib.error.HTTPError(
            "https://example.invalid/v1/messages",
            429,
            "Too Many Requests",
            None,
            io.BytesIO(b'{"error": "vendor rate limit text"}'),
        )

    return backend


def _read_invocations(log_path):
    if not log_path.exists():
        return []
    lines = log_path.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def test_ac_endpoint_003_http_429_maps_to_rate_limit_without_retry(isolated_cwd, tmp_path):
    log_path = tmp_path / "backend_invocations.jsonl"
    backend = _make_rate_limited_backend(log_path)

    response = llm_endpoint.complete(
        "Say hello.",
        "anthropic:claude-sonnet-5",
        backend=backend,
    )

    # Failure category captured as structured data, exactly "rate_limit".
    error = field(response, "model_call_error")
    assert error is not None
    assert not isinstance(error, bool)
    assert field(error, "category") == "rate_limit"

    # text is null on failure.
    assert field(response, "text") is None

    # Exactly one call to the backend: no internal retry loop.
    invocations = _read_invocations(log_path)
    assert len(invocations) == 1, (
        "expected exactly one backend call (no retry), got %d" % len(invocations)
    )