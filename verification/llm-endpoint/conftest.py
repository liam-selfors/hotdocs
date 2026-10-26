"""Fixtures for llm-endpoint's test suite.

Rewritten again for D53: the second self-hosted regeneration of
gen/llm-endpoint/llm_endpoint.py (reflecting D52's 300s timeout floor
and D53's structural --tools ""/--bare isolation requirement) returns a
plain dict from complete() and expects an injected backend to return a
dict too -- a third distinct internal convention across three
generations (object+BackendResult -> tuple -> dict), each equally
spec-conformant since interface/library.md only ever fixed the public
`complete(prompt, model, *, backend=None, **params)` signature, never
the Python shape of its return value.
"""

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "gen" / "llm-endpoint"))
import llm_endpoint  # noqa: E402


class MockBackend:
    """A scripted, dict-returning callable backend -- matches
    gen/llm-endpoint/llm_endpoint.py's own current convention exactly."""

    name = "mock"

    def __init__(self, text=None, error=None):
        self.text = text
        self.error = error
        self.calls = []

    def __call__(self, prompt, model, **params):
        self.calls.append((prompt, model, params))
        return {"text": self.text, "model": model, "backend": self.name, "model_call_error": self.error}


@pytest.fixture
def isolated_cwd(tmp_path, monkeypatch):
    """R-ENDPOINT-006 writes to .hotdocs/calls/ under the current
    directory -- redirect it to a throwaway tmp_path, never this repo's
    own real .hotdocs/."""
    monkeypatch.chdir(tmp_path)
    return tmp_path
