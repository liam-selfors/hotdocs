"""One test per AC-ENDPOINT-* criterion in
specs/components/llm-endpoint/acceptance/.
"""

import json
from pathlib import Path

import pytest

from conftest import MockBackend
import llm_endpoint
from llm_endpoint import BackendResult, UnsupportedModelError, complete


def test_ac_endpoint_001_unsupported_model_fails_before_any_call(isolated_cwd):
    # No injected backend here, deliberately -- this tests the REAL
    # resolution path (R-ENDPOINT-002). Injecting backend= bypasses
    # resolution entirely by design (it's a dependency-injection seam
    # for testing dispatch logic, not a resolution test fixture) -- that
    # bypass is covered by test_ac_endpoint_002 and friends, not this one.
    with pytest.raises(UnsupportedModelError):
        complete("hello", "gpt-5")


def test_ac_endpoint_002_mock_success(isolated_cwd):
    backend = MockBackend([BackendResult(text="hello")])
    response = complete("say hi", "claude-sonnet-5", backend=backend)
    assert response.text == "hello"
    assert response.model == "claude-sonnet-5"
    assert response.model_call_error is None
    assert len(backend.calls) == 1


def test_ac_endpoint_003_rate_limit_no_retry(isolated_cwd):
    backend = MockBackend([
        BackendResult(text=None, error_category="rate_limit", error_message="429 from backend"),
    ])
    response = complete("say hi", "claude-sonnet-5", backend=backend)
    assert response.text is None
    assert response.model_call_error["category"] == "rate_limit"
    assert len(backend.calls) == 1  # no internal retry loop


def test_ac_endpoint_004_credential_never_leaks(isolated_cwd, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-TOTALLY-SECRET-VALUE")
    backend = MockBackend([
        BackendResult(text=None, error_category="auth", error_message="401 unauthorized"),
    ])
    response = complete("say hi", "claude-sonnet-5", backend=backend)

    assert "TOTALLY-SECRET-VALUE" not in json.dumps(response.to_dict())

    calls_dir = isolated_cwd / ".hotdocs" / "calls"
    logged = [p.read_text(encoding="utf-8") for p in calls_dir.glob("*.json")]
    assert logged  # the call was actually logged
    assert all("TOTALLY-SECRET-VALUE" not in text for text in logged)
    # llm_endpoint.py itself never reads the credential at all -- the
    # above only re-confirms what the module's own design already
    # guarantees structurally (R-ENDPOINT-005).


def test_ac_endpoint_005_internal_backend_resolution(isolated_cwd):
    # A caller never names a backend -- only a model. Confirmed here by
    # calling the internal resolver directly (compiled, deterministic;
    # no real network call needed to prove resolution alone succeeds).
    backend = llm_endpoint._resolve_backend("claude-sonnet-5")
    assert backend.name == "anthropic"
    assert isinstance(backend, llm_endpoint.AnthropicBackend)


def test_ac_endpoint_006_call_log_has_two_independent_records(isolated_cwd):
    backend = MockBackend([
        BackendResult(text=None, error_category="timeout", error_message="timed out"),
    ])
    complete("first", "claude-sonnet-5", backend=backend)

    backend2 = MockBackend([BackendResult(text="ok")])
    complete("second", "claude-sonnet-5", backend=backend2)

    calls_dir = isolated_cwd / ".hotdocs" / "calls"
    records = [json.loads(p.read_text(encoding="utf-8")) for p in calls_dir.glob("*.json")]
    assert len(records) == 2
    categories = {r["model_call_error"]["category"] if r["model_call_error"] else None for r in records}
    assert categories == {"timeout", None}


def test_backend_result_rejects_both_or_neither():
    with pytest.raises(ValueError):
        BackendResult(text="x", error_category="network", error_message="y")
    with pytest.raises(ValueError):
        BackendResult(text=None)
