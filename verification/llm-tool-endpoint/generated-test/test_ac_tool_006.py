import email.message
import io
import json
import urllib.error
import urllib.request

import pytest

import llm_tool_endpoint


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


TOOL = {
    "name": "read_file",
    "description": "Read a file from the workspace.",
    "input_schema": {
        "type": "object",
        "properties": {"path": {"type": "string"}},
        "required": ["path"],
    },
}


@pytest.mark.parametrize(
    "status,category",
    [
        (401, "auth"),
        (429, "rate_limit"),
        (504, "timeout"),
        (500, "network"),
    ],
)
def test_ac_tool_006_http_error_categorized_without_leak(
    status, category, tmp_path, monkeypatch
):
    workdir = tmp_path / "work"
    workdir.mkdir()
    monkeypatch.chdir(workdir)
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "secret-key-value")

    recorded = []

    def fake_urlopen(request, timeout=None, *args, **kwargs):
        url = request.full_url if hasattr(request, "full_url") else str(request)
        headers = {}
        if hasattr(request, "header_items"):
            headers = {k.lower(): v for k, v in request.header_items()}
        body = None
        data = getattr(request, "data", None)
        if data is not None:
            if isinstance(data, (bytes, bytearray)):
                data = data.decode("utf-8")
            try:
                body = json.loads(data)
            except Exception:
                body = data
        recorded.append({"url": url, "headers": headers, "body": body})
        hdrs = email.message.Message()
        raise urllib.error.HTTPError(
            url, status, "error", hdrs, io.BytesIO(b"vendor says no")
        )

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    executed = []

    def execute(name, arguments):
        executed.append((name, arguments))
        return ("ok", False)

    result = llm_tool_endpoint.run_tool_loop(
        "sys", "go", "anthropic:claude-opus-5-5", [TOOL], execute
    )

    # Exactly one request: no retry.
    assert len(recorded) == 1, recorded

    assert field(result, "stop") == "error"

    error = field(result, "model_call_error")
    assert error is not None
    assert field(error, "category") == category

    as_dict = result if isinstance(result, dict) else result.to_dict()
    rendered = json.dumps(as_dict)
    assert "vendor says no" not in rendered
    assert "secret-key-value" not in rendered

    # No tool ran since no reply was ever received.
    assert executed == []