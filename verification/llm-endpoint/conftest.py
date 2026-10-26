"""Fixtures for llm-endpoint's test suite.

Rewritten for D51: gen/llm-endpoint/ is now the output of a real
self-hosted generation pass (generator regenerating llm-endpoint from
its own current spec), not the original hand-written bootstrap. The
self-hosted version chose a different, equally valid internal backend
convention -- a plain callable `backend(prompt, model, **params) ->
(text, error)` instead of the original's `backend.complete(...)
-> BackendResult` object -- so this MockBackend matches what the
*current* gen/llm-endpoint/ code actually expects, not the retired
convention. Every test still verifies the same AC-ENDPOINT-* criteria;
only the mock's shape changed, because that shape was never part of
the public interface spec (interface/library.md only fixes
`complete(prompt, model, *, backend=None, **params) -> ModelResponse`).
"""

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "gen" / "llm-endpoint"))
import llm_endpoint  # noqa: E402


class MockBackend:
    """A scripted, callable backend -- matches gen/llm-endpoint/llm_endpoint/
    backends/anthropic.py's own `__call__(prompt, model, **params) ->
    (text, error)` convention exactly."""

    name = "mock"

    def __init__(self, text=None, error=None):
        self.text = text
        self.error = error
        self.calls = []

    def __call__(self, prompt, model, **params):
        self.calls.append((prompt, model, params))
        return self.text, self.error


@pytest.fixture
def isolated_cwd(tmp_path, monkeypatch):
    """R-ENDPOINT-006 writes to .hotdocs/calls/ under the current
    directory -- redirect it to a throwaway tmp_path, never this repo's
    own real .hotdocs/."""
    monkeypatch.chdir(tmp_path)
    return tmp_path
