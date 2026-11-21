# hotdocs-criterion: sha256:9f3d320d2dbecaf840ba7eaf8a9db4b300abb8cd1686520d3786814f096c9e2e
import io
import urllib.error

import llm_endpoint


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def test_ac_endpoint_003_http_429_is_rate_limit_without_retry(tmp_path, monkeypatch):
    # complete() writes its call log under .hotdocs/calls/ in the current
    # directory; keep that inside a fresh temporary directory.
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)

    calls = []

    def mock_backend(prompt, model, **params):
        calls.append((prompt, model, dict(params)))
        raise urllib.error.HTTPError(
            "https://example.invalid/v1/messages",
            429,
            "Too Many Requests",
            {},
            io.BytesIO(b'{"error": "rate limited"}'),
        )

    model = "anthropic:claude-sonnet-5"
    response = llm_endpoint.complete("hello", model, backend=mock_backend)

    # Exactly one call: no internal retry loop.
    assert len(calls) == 1

    # Text is null on failure.
    assert field(response, "text") is None

    # The failure is structured data, with the exact category.
    error = field(response, "model_call_error")
    assert error is not None
    assert not isinstance(error, bool)
    category = field(error, "category")
    assert category == "rate_limit"

    # Still no second call after the response has been built.
    assert len(calls) == 1