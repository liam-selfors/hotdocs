import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "gen" / "generator"))
sys.path.insert(0, str(REPO_ROOT / "gen" / "llm-endpoint"))
sys.path.insert(0, str(REPO_ROOT / "gen" / "cache-manager"))
import generator  # noqa: E402

_NONCE_RE = re.compile(r"-----BEGIN FILE (?P<nonce>[0-9a-f]+):")


def file_block(path: str, content: str):
    """D56 -- a MockBackend result that echoes back whatever nonce this
    call's real system prompt actually used, the same way a real model
    would. Returns a callable (MockBackend's own protocol for a
    per-call-computed result) rather than a static string, since the
    nonce does not exist until generate() creates it mid-call."""

    def _build(params: dict) -> dict:
        match = _NONCE_RE.search(params.get("system_prompt", ""))
        nonce = match.group("nonce") if match else "MISSING-NONCE"
        text = f"-----BEGIN FILE {nonce}: {path}-----\n{content}\n-----END FILE {nonce}-----"
        return {"text": text, "model_call_error": None}

    return _build


class MockBackend:
    """Matches gen/llm-endpoint/llm_endpoint.py's own current backend
    convention (D53 -- a self-hosted regeneration of llm-endpoint
    returns a plain ModelResponse-shaped dict from `complete()`,
    unwrapped from whatever the injected/resolved backend returned,
    rather than D51's `(text, error)` tuple or the original's
    `BackendResult` object). `generate()` passes `llm_backend` straight
    through to `llm_endpoint.complete()`'s own `backend` parameter, and
    `generator.py`'s own `_as_dict()` adapter tolerates whichever shape
    comes back -- but an *injected* backend callable must itself return
    something dict-shaped, since `complete()` does not transform a
    caller-supplied backend's return value at all.

    A scripted result MAY be a plain dict (for error/empty-text cases
    that don't depend on the call's nonce) or a callable taking this
    call's `params` (D56 -- for a success response, which must echo back
    the one-time nonce `generate()` embeds in `system_prompt`, same as
    `file_block()` above builds)."""

    name = "mock"

    def __init__(self, results):
        self._results = list(results)
        self.calls = []

    def __call__(self, prompt, model, **params):
        self.calls.append((prompt, model, params))
        result = self._results.pop(0)
        return result(params) if callable(result) else result


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
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    return tmp_path
