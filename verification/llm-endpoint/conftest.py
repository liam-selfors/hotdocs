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


# ---------------------------------------------------------------------------
# Multi-provider helpers (D180-D183): the HTTP providers are tested by
# replacing urllib.request.urlopen -- never a real server (http.server's
# bind resolves the host name and took 35 s on this machine).
# ---------------------------------------------------------------------------

import io  # noqa: E402
import json as _json  # noqa: E402
import urllib.error  # noqa: E402
import urllib.request  # noqa: E402


class FakeReply:
    def __init__(self, body):
        self._body = body if isinstance(body, bytes) else _json.dumps(body).encode("utf-8")

    def read(self, *args):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FakeUrlopen:
    """Scripted stand-in for urllib.request.urlopen: each outcome is a
    body (dict/bytes), or an exception instance to raise."""

    def __init__(self, *outcomes):
        self.outcomes = list(outcomes)
        self.requests = []

    def __call__(self, request, timeout=None):
        self.requests.append((request, timeout))
        outcome = self.outcomes.pop(0) if self.outcomes else {}
        if isinstance(outcome, BaseException):
            raise outcome
        return FakeReply(outcome)

    @property
    def last(self):
        return self.requests[-1][0]

    def header(self, name):
        return {k.lower(): v for k, v in self.last.header_items()}.get(name.lower())

    def body(self):
        return _json.loads(self.last.data)


def http_error(code, body="", url="https://example.invalid/x"):
    return urllib.error.HTTPError(url, code, "err", {}, io.BytesIO(body.encode("utf-8")))


@pytest.fixture
def fake_urlopen(monkeypatch):
    def install(*outcomes):
        fake = FakeUrlopen(*outcomes)
        monkeypatch.setattr(urllib.request, "urlopen", fake)
        return fake

    return install


@pytest.fixture
def clean_env(monkeypatch):
    """No provider keys or config in the environment."""
    for name in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY", "VAR_HOTDOCS_CONFIG"):
        monkeypatch.delenv(name, raising=False)
