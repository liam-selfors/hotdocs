"""AC-ENDPOINT-004 (Covers: R-ENDPOINT-005).

A provider credential never appears in a ModelResponse, in a call-log
file under .hotdocs/calls/, or in a check_connection result, even when
the vendor echoes it back in an HTTP 401 body. save_config refuses an
api_key_env value that is the key itself, and writes no file.
"""

import io
import json
import urllib.error
import urllib.request

import pytest

import llm_endpoint


SECRET = "sk-SECRET-123"
KEY_VARS = ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY")
PROVIDERS_UNDER_TEST = ("anthropic", "openai", "gemini")


def _dump(value):
    """Render a returned value (dict or object) as fully as possible."""
    parts = [repr(value), str(value)]
    try:
        parts.append(json.dumps(value, default=str))
    except Exception:
        pass
    if not isinstance(value, dict):
        try:
            parts.append(repr(vars(value)))
        except TypeError:
            pass
    return "\n".join(parts)


@pytest.fixture
def secret_env(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    workdir = tmp_path / "work"
    workdir.mkdir()
    monkeypatch.chdir(workdir)
    for name in KEY_VARS:
        monkeypatch.setenv(name, SECRET)

    calls = []

    def fake_urlopen(request, timeout=None, *args, **kwargs):
        calls.append(request)
        body = json.dumps(
            {"error": {"type": "authentication_error",
                       "message": "Invalid API key: " + SECRET}}
        ).encode("utf-8")
        raise urllib.error.HTTPError(
            "https://example.invalid/endpoint",
            401,
            "Unauthorized",
            None,
            io.BytesIO(body),
        )

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    return workdir, calls


def test_secret_never_in_responses_call_log_or_check_connection(secret_env):
    workdir, _calls = secret_env

    responses = []
    for provider in PROVIDERS_UNDER_TEST:
        responses.append(llm_endpoint.complete("Say hello.", provider + ":m"))

    for resp in responses:
        assert SECRET not in _dump(resp), (
            "credential leaked into a ModelResponse: %r" % (resp,)
        )

    results = []
    for provider in PROVIDERS_UNDER_TEST:
        results.append(llm_endpoint.check_connection(provider, "m"))

    for result in results:
        assert SECRET not in _dump(result), (
            "credential leaked into a check_connection result: %r" % (result,)
        )

    calls_dir = workdir / ".hotdocs" / "calls"
    assert calls_dir.is_dir(), "complete() wrote no call log under .hotdocs/calls/"
    files = [p for p in calls_dir.rglob("*") if p.is_file()]
    assert len(files) >= len(PROVIDERS_UNDER_TEST), (
        "expected at least one call-log file per complete() call, found %d"
        % len(files)
    )
    for path in files:
        content = path.read_bytes().decode("utf-8", errors="replace")
        assert SECRET not in content, (
            "credential leaked into call-log file %s" % path
        )


def test_save_config_refuses_key_as_api_key_env(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", SECRET)
    config_path = tmp_path / "hotdocs.toml"

    with pytest.raises(ValueError) as excinfo:
        llm_endpoint.save_config(config_path, "openai", "m", api_key_env=SECRET)

    assert "never the key itself" in str(excinfo.value)
    assert not config_path.exists()