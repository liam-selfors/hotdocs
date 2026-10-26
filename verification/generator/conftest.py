import sys
from dataclasses import dataclass, field
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "gen" / "generator"))
sys.path.insert(0, str(REPO_ROOT / "gen" / "llm-endpoint"))
sys.path.insert(0, str(REPO_ROOT / "gen" / "cache-manager"))
import generator  # noqa: E402
from llm_endpoint import BackendResult  # noqa: E402


class MockBackend:
    """Same shape as llm-endpoint's own test MockBackend -- a scripted
    backend recording every call it actually received."""

    name = "mock"

    def __init__(self, results):
        self._results = list(results)
        self.calls = []

    def complete(self, prompt, model, **params):
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
