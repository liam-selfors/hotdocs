# hotdocs-criterion: sha256:3bbdacdfa29d5166222fcd64e72f19a01d063f0e0251616d2b071350a3379fe2
import io
import urllib.error

import llm_endpoint


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def test_ac_endpoint_003_http_429_is_rate_limit_without_retry(tmp_path, monkeypatch):
    # Keep the call log and any config discovery inside a fresh directory.
    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.chdir(work)
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)

    call_log = tmp_path / "backend_calls.log"

    def mock_backend(prompt, model, **params):
        with open(call_log, "a", encoding="utf-8") as fh:
            fh.write("call\n")
        raise urllib.error.HTTPError(
            "https://example.invalid/v1/messages",
            429,
            "Too Many Requests",
            {},
            io.BytesIO(b'{"error": "vendor says slow down"}'),
        )

    response = llm_endpoint.complete(
        "hello", "anthropic:claude-sonnet-5", backend=mock_backend
    )

    # Exactly one call was made to the backend: no internal retry loop.
    assert call_log.is_file(), "mock backend was never called"
    lines = [line for line in call_log.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(lines) == 1, "expected exactly one backend call, got " + repr(len(lines))

    # The failure is structured data, not a boolean.
    assert field(response, "text") is None
    error = field(response, "model_call_error")
    assert error is not None
    assert not isinstance(error, bool)
    assert field(error, "category") == "rate_limit"