# hotdocs-criterion: sha256:1f72a459df41d92c7d8b3b0b752b29daece1e0d6e6c612ddbe9fb113e7e027a9
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
def test_http_error_ends_loop_with_categorized_error(
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
        headers = dict(request.header_items()) if hasattr(request, "header_items") else {}
        data = getattr(request, "data", None)
        body = None
        if data is not None:
            try:
                body = json.loads(data.decode("utf-8"))
            except Exception:
                body = data
        recorded.append({"url": url, "headers": headers, "body": body})
        hdrs = email.message.Message()
        hdrs["Content-Type"] = "text/plain"
        raise urllib.error.HTTPError(
            url, status, "vendor says no", hdrs, io.BytesIO(b"vendor says no")
        )

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    executed = []

    def execute(name, arguments):
        executed.append((name, arguments))
        return ("ok", False)

    result = llm_tool_endpoint.run_tool_loop(
        "sys", "go", "anthropic:claude-opus-5-5", [TOOL], execute
    )

    assert len(recorded) == 1
    assert executed == []
    assert field(result, "stop") == "error"

    err = field(result, "model_call_error")
    assert err is not None
    assert field(err, "category") == category

    rendered = json.dumps(result.to_dict())
    assert "vendor says no" not in rendered
    assert "secret-key-value" not in rendered