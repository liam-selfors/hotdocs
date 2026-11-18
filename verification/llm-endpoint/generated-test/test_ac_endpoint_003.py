# hotdocs-criterion: sha256:ae834c0001bde20a3d00ac73d7528a53a8f1d5d3abcdb4f75ce2aea5a9c53d90
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
    monkeypatch.chdir(work)
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    return tmp_path


def _make_raising_backend(log_path):
    def backend(prompt, model, **params):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"prompt": prompt, "model": model}) + "\n")
        raise urllib.error.HTTPError(
            "https://example.invalid/v1/messages",
            429,
            "Too Many Requests",
            {},
            io.BytesIO(b'{"error": "rate limited"}'),
        )

    return backend


def _read_calls(log_path):
    if not log_path.exists():
        return []
    return [
        json.loads(line)
        for line in log_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_ac_endpoint_003_http_429_is_rate_limit_with_no_retry(isolated_cwd):
    log_path = isolated_cwd / "backend_calls.jsonl"
    backend = _make_raising_backend(log_path)

    response = llm_endpoint.complete(
        "Say hello.", "anthropic:claude-sonnet-5", backend=backend
    )

    # The failure is captured as structured data, not a boolean.
    error = field(response, "model_call_error")
    assert error is not None
    assert not isinstance(error, bool)
    assert field(error, "category") == "rate_limit"

    # text is null on failure.
    assert field(response, "text") is None

    # Exactly one call to the backend: no internal retry loop.
    calls = _read_calls(log_path)
    assert len(calls) == 1, f"expected exactly one backend call, got {len(calls)}"