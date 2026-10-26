import sys
from dataclasses import dataclass, field
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "gen" / "generator"))
sys.path.insert(0, str(REPO_ROOT / "gen" / "llm-endpoint"))
sys.path.insert(0, str(REPO_ROOT / "gen" / "cache-manager"))
import generator  # noqa: E402


class MockBackend:
    """Matches gen/llm-endpoint/llm_endpoint/'s own current backend
    convention (D51 -- a self-hosted regeneration of llm-endpoint chose
    a plain-callable shape, `backend(prompt, model, **params) ->
    (text, error)`, instead of the original `.complete() -> BackendResult`
    object). `generate()` passes `llm_backend` straight through to
    `llm_endpoint.complete()`'s own `backend` parameter, so this mock
    must match whatever that package currently expects, not a retired
    convention."""

    name = "mock"

    def __init__(self, results):
        self._results = list(results)
        self.calls = []

    def __call__(self, prompt, model, **params):
        self.calls.append((prompt, model, params))
        result = self._results.pop(0)
        return result() if callable(result) else result


@dataclass
class FakeBundle:
    component_id: str = "comp-foo"
    spec_bundle_hash: str = "sha256:fakehash"
    spec: str = "FAKE SPEC TEXT"
    interface: str = "FAKE INTERFACE TEXT"
    constraints: str = "FAKE CONSTRAINTS TEXT"
    dependency_interfaces: dict = field(default_factory=dict)
    dependency_context: dict = field(default_factory=dict)
    vars: dict = field(default_factory=dict)
    glossary: str = "FAKE GLOSSARY TEXT"
    hint_code: dict | None = None


@pytest.fixture
def repo_root(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    return tmp_path
