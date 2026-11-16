"""AC-GEN-005 (covers R-GEN-005).

Given a cache-manager pre-populated with a result for a given
  (spec_bundle_hash, gate_inputs_hash, gate_version, model_pin) key
When generate is called with inputs matching that key
Then the cached result is returned and the mock model is never called
"""

import collections.abc
import dataclasses
import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest

import generator


MODEL = "claude-sonnet-5"
COMPONENT_ID = "comp-foo"
SPEC_BUNDLE_HASH = "sha256:" + hashlib.sha256(b"ac-gen-005 synthetic bundle").hexdigest()

CACHED_FILES = {
    "foo.py": "def foo(x):\n    # CACHED-CANDIDATE\n    return 2 * x\n",
}
MODEL_FILES_MARKER = "# MODEL-PRODUCED-CANDIDATE"


def _field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


@dataclasses.dataclass
class SpecBundle(collections.abc.Mapping):
    """A SpecBundle-shaped value: the documented fields, in order, and
    read-only mapping access (``bundle["spec"]``, ``bundle.get("spec")``)."""

    component_id: str
    spec_bundle_hash: str
    spec: str
    interface: str
    constraints: str
    dependency_interfaces: dict = dataclasses.field(default_factory=dict)
    dependency_context: dict = dataclasses.field(default_factory=dict)
    dependency_usage: dict = dataclasses.field(default_factory=dict)
    vars: dict = dataclasses.field(default_factory=dict)
    glossary: str = ""
    hint_code: dict = None

    def _names(self):
        return [f.name for f in dataclasses.fields(self)]

    def __getitem__(self, key):
        if key not in self._names():
            raise KeyError(key)
        return getattr(self, key)

    def __iter__(self):
        return iter(self._names())

    def __len__(self):
        return len(self._names())


def _make_bundle():
    return SpecBundle(
        component_id=COMPONENT_ID,
        spec_bundle_hash=SPEC_BUNDLE_HASH,
        spec="# Foo\n\n## Purpose\n\nFoo doubles a number.\n\n# R-FOO-001\n\n"
        "**R-FOO-001** — `foo(x)` MUST return `2 * x`.",
        interface="# Library\n\n```\nfoo(x: int) -> int\n```",
        constraints="# Constraints\n\nNone.",
        glossary="# Glossary\n\n- **Foo** — a test term.",
        hint_code=None,
    )


def _load_cache_manager(monkeypatch):
    gen_dir = next(
        p for p in Path(generator.__file__).resolve().parents if p.name == "gen"
    )
    base = gen_dir / "cache-manager"
    flat = base / "cache_manager.py"
    if flat.is_file():
        spec = importlib.util.spec_from_file_location("cache_manager", flat)
    else:
        pkg = base / "cache_manager" / "__init__.py"
        spec = importlib.util.spec_from_file_location(
            "cache_manager", pkg, submodule_search_locations=[str(pkg.parent)]
        )
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, "cache_manager", module)
    spec.loader.exec_module(module)
    return module


def _gate_inputs_hash(retry_feedback):
    text = json.dumps(sorted(retry_feedback or []), sort_keys=True)
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def _make_mock_backend(log_path):
    def backend(prompt, model, **params):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"model": model, "params": sorted(params)}) + "\n")
        match = re.search(r"-----BEGIN FILE ([0-9a-f]{32}):", prompt)
        nonce = match.group(1) if match else "0" * 32
        text = (
            f"-----BEGIN FILE {nonce}: foo.py-----\n"
            f"def foo(x):\n    {MODEL_FILES_MARKER}\n    return x + x\n"
            f"-----END FILE {nonce}-----\n"
            f"-----END REPLY {nonce}-----\n"
        )
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    return backend


@pytest.mark.parametrize(
    "retry_feedback",
    [None, ["R-FOO-002", "R-FOO-001"]],
    ids=["blind", "informed"],
)
def test_cache_hit_returns_cached_result_without_model_call(
    tmp_path, monkeypatch, retry_feedback
):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)

    log_path = tmp_path / "mock_model_calls.log"
    backend = _make_mock_backend(log_path)

    cache_manager = _load_cache_manager(monkeypatch)

    key = cache_manager.CacheKey(
        spec_bundle_hash=SPEC_BUNDLE_HASH,
        gate_inputs_hash=_gate_inputs_hash(retry_feedback),
        gate_version=generator.GATE_VERSION,
        model_pin=MODEL,
    )
    payload = {
        "component_id": COMPONENT_ID,
        "spec_bundle_hash": SPEC_BUNDLE_HASH,
        "model": MODEL,
        "prompt_version": generator.PROMPT_VERSION,
        "cache_hit": False,
        "files": dict(CACHED_FILES),
        "model_call_error": None,
        "refused": None,
        "retry_feedback": list(retry_feedback) if retry_feedback is not None else None,
        "mode": "single",
        "transcript_sha256": None,
        "turns": 1,
        "tool_calls": 0,
        "isolation": None,
    }
    cached = cache_manager.CachedResult(
        gate_type="generator",
        payload=payload,
        stored_at=cache_manager.now_iso(),
    )
    cache_manager.put(key, cached, repo_root=repo_root)

    # Precondition: the cache really holds an entry under that key.
    pre = cache_manager.get(key, repo_root=repo_root)
    assert not isinstance(pre, cache_manager.Miss), "fixture failed to pre-populate the cache"

    bundle = _make_bundle()
    result = generator.generate(
        bundle,
        MODEL,
        list(retry_feedback) if retry_feedback is not None else None,
        repo_root=repo_root,
        llm_backend=backend,
    )

    # The mock model was never called.
    assert not log_path.exists() or log_path.read_text(encoding="utf-8").strip() == "", (
        "the mock model was called despite a cache hit: "
        + log_path.read_text(encoding="utf-8")
    )

    # The cached result is what came back.
    assert _field(result, "cache_hit") is True
    files = _field(result, "files")
    assert dict(files) == CACHED_FILES
    assert all(MODEL_FILES_MARKER not in content for content in files.values())
    assert _field(result, "model_call_error") is None
    assert _field(result, "refused") is None
    assert _field(result, "component_id") == COMPONENT_ID
    assert _field(result, "spec_bundle_hash") == SPEC_BUNDLE_HASH
    assert _field(result, "model") == MODEL
    assert _field(result, "prompt_version") == generator.PROMPT_VERSION