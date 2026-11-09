"""One test per AC-ENDPOINT-* criterion in
specs/components/llm-endpoint/acceptance/.

Rewritten again for D53 against the second self-hosted gen/llm-endpoint/
llm_endpoint.py -- see conftest.py's docstring for why MockBackend's
shape changed again, and complete()'s own return value is now accessed
by dict key rather than attribute.
"""

import json

import pytest

from conftest import MockBackend
import llm_endpoint
from llm_endpoint import complete


def test_ac_endpoint_001_unsupported_model_fails_before_any_call(isolated_cwd):
    with pytest.raises(llm_endpoint.ModelResolutionError):
        complete("hello", "gpt-5")


def test_ac_endpoint_002_mock_success(isolated_cwd):
    backend = MockBackend(text="hello")
    response = complete("say hi", "claude-sonnet-5", backend=backend)
    assert response["text"] == "hello"
    assert response["model"] == "claude-sonnet-5"
    assert response["model_call_error"] is None
    assert len(backend.calls) == 1


def test_ac_endpoint_003_rate_limit_no_retry(isolated_cwd):
    backend = MockBackend(error={"category": "rate_limit", "message": "429 from backend"})
    response = complete("say hi", "claude-sonnet-5", backend=backend)
    assert response["text"] is None
    assert response["model_call_error"]["category"] == "rate_limit"
    assert len(backend.calls) == 1  # no internal retry loop


def test_ac_endpoint_004_credential_never_leaks(isolated_cwd, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-TOTALLY-SECRET-VALUE")
    backend = MockBackend(error={"category": "auth", "message": "401 unauthorized"})
    response = complete("say hi", "claude-sonnet-5", backend=backend)

    assert "TOTALLY-SECRET-VALUE" not in json.dumps(response)

    calls_dir = isolated_cwd / ".hotdocs" / "calls"
    logged = [p.read_text(encoding="utf-8") for p in calls_dir.glob("*.json")]
    assert logged
    assert all("TOTALLY-SECRET-VALUE" not in text for text in logged)


def test_ac_endpoint_005_internal_backend_resolution(isolated_cwd):
    backend_name = llm_endpoint.resolve_backend_name("claude-sonnet-5")
    assert backend_name == "anthropic"


def test_ac_endpoint_006_call_log_has_two_independent_records(isolated_cwd):
    backend = MockBackend(error={"category": "timeout", "message": "timed out"})
    complete("first", "claude-sonnet-5", backend=backend)

    backend2 = MockBackend(text="ok")
    complete("second", "claude-sonnet-5", backend=backend2)

    calls_dir = isolated_cwd / ".hotdocs" / "calls"
    records = [json.loads(p.read_text(encoding="utf-8")) for p in calls_dir.glob("*.json")]
    assert len(records) == 2
    categories = {r.get("model_call_error", {}).get("category") if r.get("model_call_error") else None for r in records}
    assert categories == {"timeout", None}


class _FakeCompleted:
    def __init__(self, returncode=0, stdout="ok", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_d82_safe_mode_dispatched_without_api_key(isolated_cwd, clean_env, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        return _FakeCompleted()

    monkeypatch.setattr(llm_endpoint.subprocess, "run", fake_run)
    response = llm_endpoint.complete("say hi", "claude-sonnet-5")

    assert "--safe-mode" in captured["cmd"]
    assert "--bare" not in captured["cmd"]
    assert response["text"] == "ok"
    assert response["model_call_error"] is None


def test_d82_bare_dispatched_with_api_key(isolated_cwd, clean_env, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-fake-for-this-test-only")
    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        return _FakeCompleted()

    monkeypatch.setattr(llm_endpoint.subprocess, "run", fake_run)
    llm_endpoint.complete("say hi", "claude-sonnet-5")

    assert "--bare" in captured["cmd"]
    assert "--safe-mode" not in captured["cmd"]


def test_d82_not_logged_in_on_stdout_classifies_as_auth(isolated_cwd, clean_env, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    def fake_run(cmd, **kwargs):
        return _FakeCompleted(returncode=1, stdout="Not logged in · Please run /login", stderr="")

    monkeypatch.setattr(llm_endpoint.subprocess, "run", fake_run)
    response = llm_endpoint.complete("say hi", "claude-sonnet-5")

    assert response["text"] is None
    assert response["model_call_error"]["category"] == "auth"
