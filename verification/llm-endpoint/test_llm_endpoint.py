"""One test per AC-ENDPOINT-* criterion in
specs/components/llm-endpoint/acceptance/.

Rewritten for D51 against the self-hosted gen/llm-endpoint/ package --
see conftest.py's docstring for why MockBackend's shape changed.
"""

import json

import pytest

from conftest import MockBackend
import llm_endpoint
from llm_endpoint import complete


def test_ac_endpoint_001_unsupported_model_fails_before_any_call(isolated_cwd):
    with pytest.raises(llm_endpoint.UnknownModelBackendError):
        complete("hello", "gpt-5")


def test_ac_endpoint_002_mock_success(isolated_cwd):
    backend = MockBackend(text="hello")
    response = complete("say hi", "claude-sonnet-5", backend=backend)
    assert response.text == "hello"
    assert response.model == "claude-sonnet-5"
    assert response.model_call_error is None
    assert len(backend.calls) == 1


def test_ac_endpoint_003_rate_limit_no_retry(isolated_cwd):
    backend = MockBackend(error={"category": "rate_limit", "message": "429 from backend"})
    response = complete("say hi", "claude-sonnet-5", backend=backend)
    assert response.text is None
    assert response.model_call_error["category"] == "rate_limit"
    assert len(backend.calls) == 1  # no internal retry loop


def test_ac_endpoint_004_credential_never_leaks(isolated_cwd, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-TOTALLY-SECRET-VALUE")
    backend = MockBackend(error={"category": "auth", "message": "401 unauthorized"})
    response = complete("say hi", "claude-sonnet-5", backend=backend)

    assert "TOTALLY-SECRET-VALUE" not in json.dumps(response.to_dict())

    calls_dir = isolated_cwd / ".hotdocs" / "calls"
    logged = [p.read_text(encoding="utf-8") for p in calls_dir.glob("*.json")]
    assert logged
    assert all("TOTALLY-SECRET-VALUE" not in text for text in logged)


def test_ac_endpoint_005_internal_backend_resolution(isolated_cwd):
    from llm_endpoint.resolve import resolve_backend
    backend = resolve_backend("claude-sonnet-5")
    assert backend.name == "anthropic"


def test_ac_endpoint_006_call_log_has_two_independent_records(isolated_cwd):
    backend = MockBackend(error={"category": "timeout", "message": "timed out"})
    complete("first", "claude-sonnet-5", backend=backend)

    backend2 = MockBackend(text="ok")
    complete("second", "claude-sonnet-5", backend=backend2)

    calls_dir = isolated_cwd / ".hotdocs" / "calls"
    records = [json.loads(p.read_text(encoding="utf-8")) for p in calls_dir.glob("*.json")]
    assert len(records) == 2
    categories = {r["model_call_error"]["category"] if r["model_call_error"] else None for r in records}
    assert categories == {"timeout", None}

