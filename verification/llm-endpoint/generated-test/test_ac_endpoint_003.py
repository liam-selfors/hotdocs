import io
import json
import urllib.error
import urllib.request

import pytest

import llm_endpoint


def _field(value, name):
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def test_ac_endpoint_003_http_429_maps_to_rate_limit_without_retry(tmp_path, monkeypatch):
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    monkeypatch.chdir(work_dir)
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)

    call_log = tmp_path / "backend_calls.log"
    urlopen_log = tmp_path / "urlopen_calls.log"

    def _guard_urlopen(*args, **kwargs):
        with open(urlopen_log, "a", encoding="utf-8") as fh:
            fh.write("urlopen\n")
        raise AssertionError("real network must not be reached when a backend is injected")

    monkeypatch.setattr(urllib.request, "urlopen", _guard_urlopen)

    def mock_backend(prompt, model, **params):
        with open(call_log, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"prompt": prompt, "model": model}) + "\n")
        raise urllib.error.HTTPError(
            "https://example.invalid/v1/messages",
            429,
            "Too Many Requests",
            {},
            io.BytesIO(b'{"error": "vendor rate limit text"}'),
        )

    model = "anthropic:claude-sonnet-5"
    response = llm_endpoint.complete("hello", model, backend=mock_backend)

    assert response is not None

    # Exactly one call to the mock backend: no internal retry loop.
    assert call_log.exists(), "mock backend was never invoked"
    lines = [ln for ln in call_log.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(lines) == 1, f"expected exactly one backend call, got {len(lines)}"

    # No real network call was made either.
    assert not urlopen_log.exists()

    # text is null.
    assert _field(response, "text") is None

    # model_call_error is structured data, not a boolean.
    error = _field(response, "model_call_error")
    assert error is not None
    assert not isinstance(error, bool)
    category = _field(error, "category")
    assert category == "rate_limit"