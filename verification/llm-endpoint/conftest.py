"""Fixtures for llm-endpoint's test suite.

Every test here uses an injected mock backend (interface/library.md's
`backend` parameter, D47) -- never a real network call. The real
`AnthropicBackend` (which shells out to the `claude` CLI and costs real
money per D46) is verified separately, once, manually -- see
BOOTSTRAP.md -- not on every test run.
"""

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "gen" / "llm-endpoint"))
import llm_endpoint  # noqa: E402


class MockBackend:
    """A scripted backend: pass a list of BackendResult-producing
    callables (or plain BackendResult instances), one consumed per call.
    Records every (prompt, model, params) it was actually called with,
    so a test can assert on call count -- e.g. confirming no retry."""

    name = "mock"

    def __init__(self, results):
        self._results = list(results)
        self.calls = []

    def complete(self, prompt, model, **params):
        self.calls.append((prompt, model, params))
        result = self._results.pop(0)
        return result() if callable(result) else result


@pytest.fixture
def isolated_cwd(tmp_path, monkeypatch):
    """R-ENDPOINT-006 writes to .hotdocs/calls/ under the current
    directory -- redirect it to a throwaway tmp_path, never this repo's
    own real .hotdocs/."""
    monkeypatch.chdir(tmp_path)
    return tmp_path
