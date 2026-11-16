"""AC-GEN-012 (Covers: R-GEN-011).

Given a mock model configured to hang (never respond) and the SDK's own
default timeout, when generate is called, then the call eventually
completes with model_call_error set (not an unbounded hang), and the mock
model records exactly one call attempt: no internal retry occurred.

The mock emulates "hang until the SDK's own timeout fires": it blocks for
a short while and then raises the timeout error the SDK raises when its
default timeout expires. An injected backend is never itself bounded by
`llm-endpoint`, so a literally infinite block would only test the test
harness. The test also guards against a real unbounded hang by running
`generate` in a worker thread with a generous join deadline.
"""

import threading
import time
from dataclasses import dataclass, field as dc_field
from pathlib import Path

import pytest

import generator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


@dataclass
class _Bundle:
    """A SpecBundle-shaped value: documented fields in order, plus
    read-only mapping access (`bundle["spec"]`, `bundle.get("spec")`)."""

    component_id: str
    spec_bundle_hash: str
    spec: str
    interface: str
    constraints: str
    dependency_interfaces: dict = dc_field(default_factory=dict)
    dependency_context: dict = dc_field(default_factory=dict)
    dependency_usage: dict = dc_field(default_factory=dict)
    vars: dict = dc_field(default_factory=dict)
    glossary: str = ""
    hint_code: object = None

    def __getitem__(self, key):
        try:
            return getattr(self, key)
        except AttributeError:
            raise KeyError(key)

    def get(self, key, default=None):
        return getattr(self, key, default)

    def keys(self):
        return [
            "component_id", "spec_bundle_hash", "spec", "interface",
            "constraints", "dependency_interfaces", "dependency_context",
            "dependency_usage", "vars", "glossary", "hint_code",
        ]

    def __iter__(self):
        return iter(self.keys())

    def __contains__(self, key):
        return key in self.keys()


def _make_bundle():
    return _Bundle(
        component_id="comp-foo",
        spec_bundle_hash="sha256:" + "ab" * 32,
        spec=(
            "# Foo\n\n## Purpose\n\nFoo doubles a number.\n\n"
            "# R-FOO-001\n\n**R-FOO-001** \u2014 `foo(x)` MUST return `2 * x`."
        ),
        interface="# Library\n\n```\nfoo(x: int) -> int\n```",
        constraints="# Constraints\n\nNone.",
        glossary="# Glossary\n\n- **Foo** \u2014 a test term.",
        hint_code=None,
    )


def test_hanging_model_yields_single_attempt_model_call_error(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    workdir = tmp_path / "cwd"
    workdir.mkdir()
    monkeypatch.chdir(workdir)
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)

    call_log = tmp_path / "mock_calls.log"

    def hanging_backend(prompt, model, **params):
        # Record this call attempt in a test-controlled file.
        with open(call_log, "a", encoding="utf-8") as fh:
            fh.write("call\n")
        # "Hang": never produce a reply; the SDK's own default timeout then
        # fires and surfaces as a timeout error.
        time.sleep(0.5)
        raise TimeoutError("timed out waiting for model response")

    bundle = _make_bundle()
    outcome = {}

    def run():
        try:
            outcome["result"] = generator.generate(
                bundle,
                "claude-sonnet-5",
                None,
                repo_root=repo_root,
                llm_backend=hanging_backend,
            )
        except BaseException as exc:  # surfaced to the main thread below
            outcome["error"] = exc

    worker = threading.Thread(target=run, daemon=True)
    worker.start()
    worker.join(timeout=120)

    # Not an unbounded hang: the call completed.
    assert not worker.is_alive(), "generate() did not return: unbounded hang"
    if "error" in outcome:
        raise outcome["error"]
    result = outcome["result"]

    # Completed with model_call_error set.
    error = field(result, "model_call_error")
    assert error is not None
    assert isinstance(error, dict)
    assert "category" in error and "message" in error
    assert field(result, "files") == {}
    assert field(result, "refused") is None
    assert field(result, "cache_hit") is False

    # Exactly one call attempt: no internal retry. Wait briefly so that any
    # background retry would have had a chance to record itself.
    time.sleep(1.0)
    assert call_log.is_file(), "the mock model was never called"
    calls = [line for line in call_log.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(calls) == 1, f"expected exactly one model call attempt, got {len(calls)}"