import json
import re
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "gen" / "generator"))
sys.path.insert(0, str(REPO_ROOT / "gen" / "cache-manager"))
import generator  # noqa: E402
import cache_manager  # noqa: E402  -- for test-side CacheKey/CachedResult construction only; the installed generator.py itself loads its own copy dynamically per call (R-GEN-014)

_NONCE_RE = re.compile(r"-----BEGIN FILE (?P<nonce>\S+):")


def file_block(path: str, content: str):
    """D58 -- the installed generator.py (the D57-fixed self-hosted
    candidate) embeds its nonce directly in the prompt it sends to
    llm_endpoint.complete(), not in a separate system_prompt parameter
    (unlike the hand-authored bootstrap this replaced). Returns a
    callable (MockBackend's own protocol for a per-call-computed
    result), since the nonce does not exist until generate() creates it
    mid-call."""

    def _build(prompt: str, model: str, **params: object) -> dict:
        match = _NONCE_RE.search(prompt)
        nonce = match.group("nonce") if match else "MISSING-NONCE"
        text = f"-----BEGIN FILE {nonce}: {path}-----\n{content}\n-----END FILE {nonce}-----"
        return {"text": text, "model_call_error": None}

    return _build


class MockBackend:
    """Matches llm_endpoint.complete()'s own injected-backend contract:
    `backend(prompt, model, **params) -> ModelResponse`-shaped dict. A
    scripted result MAY be a plain dict (for error/empty-text cases that
    don't depend on the call's nonce) or a callable taking this call's
    `(prompt, model, **params)` (D58 -- for a success response, which
    must echo back the one-time nonce `generate()` embeds in `prompt`
    itself, same as `file_block()` above builds)."""

    name = "mock"

    def __init__(self, results):
        self._results = list(results)
        self.calls = []

    def __call__(self, prompt, model, **params):
        self.calls.append((prompt, model, params))
        result = self._results.pop(0)
        return result(prompt, model, **params) if callable(result) else result


@dataclass
class FakeBundle:
    component_id: str = "comp-foo"
    spec_bundle_hash: str = "sha256:fakehash"
    spec: str = "FAKE SPEC TEXT"
    interface: str = "FAKE INTERFACE TEXT"
    constraints: str = "FAKE CONSTRAINTS TEXT"
    dependency_interfaces: dict = field(default_factory=dict)
    dependency_context: dict = field(default_factory=dict)
    dependency_usage: dict = field(default_factory=dict)
    vars: dict = field(default_factory=dict)
    glossary: str = "FAKE GLOSSARY TEXT"
    hint_code: dict | None = None


@pytest.fixture
def repo_root(tmp_path, monkeypatch):
    """D58 -- the installed generator.py loads cache-manager/llm-endpoint
    dynamically, per call, from whatever repo_root it's given (R-GEN-014)
    rather than via a path fixed relative to its own installed location.
    A real copy of each must actually exist under tmp_path/gen/ for any
    test to reach past the first dependency load."""
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    shutil.copytree(REPO_ROOT / "gen" / "cache-manager", tmp_path / "gen" / "cache-manager")
    shutil.copytree(REPO_ROOT / "gen" / "llm-endpoint", tmp_path / "gen" / "llm-endpoint")
    return tmp_path
