# hotdocs-criterion: sha256:9f75d0e86bb7b6cc26b3687037b64af41d80aea14e48684354dfd17c190e7314
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
    "description": "Read a file.",
    "input_schema": {
        "type": "object",
        "properties": {"path": {"type": "string"}},
        "required": ["path"],
    },
}


@pytest.mark.parametrize(
    "status, category",
    [
        (401, "auth"),
        (429, "rate_limit"),
        (504, "timeout"),
        (500, "network"),
    ],
)
def test_ac_tool_006_http_error_categorized_without_leaking(
    status, category, tmp_path, monkeypatch
):
    workdir = tmp_path / "empty"
    workdir.mkdir()
    monkeypatch.chdir(workdir)
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "secret-key-value")

    recorded = []

    def fake_urlopen(request, timeout=None, *args, **kwargs):
        url = request.full_url if hasattr(request, "full_url") else str(request)
        headers = dict(request.header_items()) if hasattr(request, "header_items") else {}
        data = getattr(request, "data", None)
        body = None
        if data is not None:
            try:
                body = json.loads(data.decode("utf-8"))
            except Exception:
                body = data
        recorded.append({"url": url, "headers": headers, "body": body, "timeout": timeout})
        hdrs = email.message.Message()
        raise urllib.error.HTTPError(
            url, status, "Error", hdrs, io.BytesIO(b"vendor says no")
        )

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    executed = []

    def execute(name, arguments):
        executed.append((name, arguments))
        return ("ok", False)

    result = llm_tool_endpoint.run_tool_loop(
        "sys", "go", "anthropic:claude-opus-5-5", [TOOL], execute
    )

    assert len(recorded) == 1, "expected exactly one request, got " + repr(len(recorded))
    assert field(result, "stop") == "error"

    error = field(result, "model_call_error")
    assert error is not None
    assert field(error, "category") == category

    rendered = json.dumps(result.to_dict())
    assert "vendor says no" not in rendered
    assert "secret-key-value" not in rendered