# hotdocs-criterion: sha256:6ed9ce064d8b05328d951fc7f51208fd6485fbb1f4cc068567f78dd06a04154d
"""AC-GEN-012 (covers R-GEN-011): a hanging model call is not retried.

Given a mock model configured to hang (never respond) and the SDK's own
default timeout, when generate is called, then the call eventually
completes with model_call_error set (not an unbounded hang), and the mock
model records exactly one call attempt: no internal retry occurred.

A test cannot wait out a real 600-second SDK timeout, so the mock models
the hang as the SDK would surface it. It blocks for a short while with no
reply, then returns the ModelResponse the SDK produces once its own default
timeout expires: a `timeout` model_call_error. The test runs `generate` in a
worker thread with a generous bound, so an unbounded hang or a retry loop
fails the test instead of stalling the run.
"""

import threading
import time
import uuid

import generator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


class FakeBundle:
    """An object with the SpecBundle fields, readable as attributes or as a mapping."""

    _FIELDS = (
        "component_id",
        "spec_bundle_hash",
        "spec",
        "interface",
        "constraints",
        "dependency_interfaces",
        "dependency_context",
        "dependency_usage",
        "vars",
        "glossary",
        "hint_code",
    )

    def __init__(self, **kwargs):
        for name in self._FIELDS:
            setattr(self, name, kwargs.get(name))

    def __getitem__(self, key):
        if key not in self._FIELDS:
            raise KeyError(key)
        return getattr(self, key)

    def get(self, key, default=None):
        if key not in self._FIELDS:
            return default
        return getattr(self, key)

    def keys(self):
        return list(self._FIELDS)

    def __iter__(self):
        return iter(self._FIELDS)

    def __len__(self):
        return len(self._FIELDS)

    def __contains__(self, key):
        return key in self._FIELDS


def make_bundle():
    return FakeBundle(
        component_id="comp-hangfoo",
        spec_bundle_hash="sha256:" + uuid.uuid4().hex + uuid.uuid4().hex,
        spec="# Hangfoo\n\n**R-HANGFOO-001** — `foo(x)` MUST return `2 * x`.",
        interface="# Library\n\n```\nfoo(x: int) -> int\n```",
        constraints="# Constraints\n\nNone.",
        dependency_interfaces={},
        dependency_context={},
        dependency_usage={},
        vars={},
        glossary="# Glossary\n\n- **Foo** — a test term.",
        hint_code=None,
    )


def test_hanging_model_call_is_attempted_exactly_once(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    call_log = tmp_path / "calls.log"
    call_log.write_text("", encoding="utf-8")

    hang_seconds = 0.5

    def hanging_backend(prompt, model, **params):
        # Record the attempt before "hanging", so even a call that is
        # later abandoned still counts.
        with open(call_log, "a", encoding="utf-8") as fh:
            fh.write("call\n")
        # The model never replies; the SDK's own default timeout is what
        # ends the wait, surfaced as a timeout model_call_error.
        time.sleep(hang_seconds)
        return {
            "text": None,
            "model": model,
            "backend": "mock-hang",
            "model_call_error": {
                "category": "timeout",
                "message": "model did not respond before the default timeout",
            },
        }

    outcome = {}

    def run():
        try:
            outcome["result"] = generator.generate(
                make_bundle(),
                "mock-hang-model",
                None,
                repo_root=repo_root,
                llm_backend=hanging_backend,
            )
        except BaseException as exc:  # surfaced below
            outcome["error"] = exc

    worker = threading.Thread(target=run, daemon=True)
    worker.start()
    worker.join(timeout=60)

    assert not worker.is_alive(), (
        "generate did not complete: an unbounded hang or an internal retry loop"
    )
    assert "error" not in outcome, "generate raised: " + repr(outcome.get("error"))
    result = outcome["result"]

    error = field(result, "model_call_error")
    assert error, "expected model_call_error to be set, got " + repr(error)
    assert field(result, "refused") is None
    assert not field(result, "files")
    assert field(result, "cache_hit") is False

    calls = [line for line in call_log.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(calls) == 1, (
        "expected exactly one model call attempt (no internal retry), got " + repr(len(calls))
    )