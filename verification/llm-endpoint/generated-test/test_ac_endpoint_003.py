# hotdocs-criterion: sha256:a7254a7b0bb8bda7a2033c247e18af1f55d64fc4a45ac674de81578eec16b60a
import io
import urllib.error

import llm_endpoint


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def test_ac_endpoint_003_http_429_is_rate_limit_with_no_retry(tmp_path, monkeypatch):
    workdir = tmp_path / "work"
    workdir.mkdir()
    monkeypatch.chdir(workdir)
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)

    log_path = tmp_path / "backend_calls.log"

    def mock_backend(prompt, model, **params):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write("call\n")
        raise urllib.error.HTTPError(
            "https://example.invalid/v1/messages",
            429,
            "Too Many Requests",
            {},
            io.BytesIO(b'{"error": "vendor rate limit text"}'),
        )

    model = "anthropic:claude-sonnet-5"
    response = llm_endpoint.complete("Hello there", model, backend=mock_backend)

    error = field(response, "model_call_error")
    assert error is not None
    assert not isinstance(error, bool)
    assert field(error, "category") == "rate_limit"
    assert field(response, "text") is None

    assert log_path.is_file()
    calls = [line for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(calls) == 1