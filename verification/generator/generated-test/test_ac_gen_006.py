import generator

import hashlib
import importlib.util
import json
import re
import sys
from collections.abc import Mapping
from dataclasses import dataclass, field as dc_field, fields
from pathlib import Path

import pytest


MODEL = "anthropic:claude-sonnet-5"
RETRY_FEEDBACK = ["R-FOO-001"]
FOO_CONTENT = "def foo(x):\n    return 2 * x\n"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


# ---------------------------------------------------------------------------
# A SpecBundle-shaped value: a dataclass with SpecBundle's fields, in order,
# that also reads as a read-only mapping.
# ---------------------------------------------------------------------------
@dataclass(frozen=True, eq=False)
class FakeSpecBundle(Mapping):
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
        if key in {f.name for f in fields(self)}:
            return getattr(self, key)
        raise KeyError(key)

    def __iter__(self):
        return iter([f.name for f in fields(self)])

    def __len__(self):
        return len(fields(self))


def _make_bundle():
    spec = (
        "# Foo\n\n## Purpose\n\nFoo doubles a number.\n\n"
        "# R-FOO-001\n\n**R-FOO-001** — `foo(x)` MUST return `2 * x`."
    )
    interface = "# Library\n\n```\nfoo(x: int) -> int\n```"
    constraints = "# Constraints\n\nNone."
    glossary = "# Glossary\n\n- **Foo** — a test term."
    digest = hashlib.sha256(
        json.dumps([spec, interface, constraints, glossary]).encode("utf-8")
    ).hexdigest()
    return FakeSpecBundle(
        component_id="comp-foo",
        spec_bundle_hash="sha256:" + digest,
        spec=spec,
        interface=interface,
        constraints=constraints,
        glossary=glossary,
        hint_code=None,
    )


# ---------------------------------------------------------------------------
# Loading the tool's real cache_manager to inspect the cache.
# ---------------------------------------------------------------------------
def _tool_root():
    gen = next(
        p for p in Path(generator.__file__).resolve().parents if p.name == "gen"
    )
    return gen.parent


def _load_cache_manager():
    base = _tool_root() / "gen" / "cache-manager"
    flat = base / "cache_manager.py"
    module_name = "_ac_gen_006_cache_manager"
    if flat.is_file():
        spec = importlib.util.spec_from_file_location(module_name, flat)
    else:
        pkg = base / "cache_manager" / "__init__.py"
        spec = importlib.util.spec_from_file_location(
            module_name, pkg, submodule_search_locations=[str(pkg.parent)]
        )
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _cache_key(cache_manager, bundle, retry_feedback, model):
    gate_inputs_hash = "sha256:" + hashlib.sha256(
        json.dumps(sorted(retry_feedback or []), sort_keys=True).encode("utf-8")
    ).hexdigest()
    return cache_manager.CacheKey(
        spec_bundle_hash=bundle.spec_bundle_hash,
        gate_inputs_hash=gate_inputs_hash,
        gate_version=generator.GATE_VERSION,
        model_pin=model,
    )


# ---------------------------------------------------------------------------
# Mock llm backend: backend(prompt, model, **params) -> ModelResponse dict,
# recording each invocation in a file the test controls.
# ---------------------------------------------------------------------------
def _make_backend(log_path, mode="ok"):
    def backend(prompt, model, **params):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"model": model}) + "\n")
        if mode == "error":
            return {
                "text": None,
                "model": model,
                "backend": "mock",
                "model_call_error": {
                    "category": "network",
                    "message": "mock backend failure",
                },
            }
        nonce = re.search(r"-----BEGIN FILE ([0-9a-f]{32}):", prompt).group(1)
        text = (
            "Here is the implementation.\n"
            f"-----BEGIN FILE {nonce}: foo.py-----\n"
            f"{FOO_CONTENT}"
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


def _call_count(log_path):
    if not Path(log_path).is_file():
        return 0
    return len(
        [l for l in Path(log_path).read_text(encoding="utf-8").splitlines() if l.strip()]
    )


def _entry_count(cache_manager, repo_root):
    stats = cache_manager.stats(repo_root=repo_root)
    return field(stats, "entry_count")


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    monkeypatch.chdir(cwd)
    log_path = tmp_path / "backend_calls.log"
    return repo_root, log_path


def test_generate_does_not_write_cache_and_commit_cache_does(env):
    repo_root, log_path = env
    cache_manager = _load_cache_manager()
    bundle = _make_bundle()
    backend = _make_backend(log_path, mode="ok")
    key = _cache_key(cache_manager, bundle, RETRY_FEEDBACK, MODEL)

    # Empty cache to begin with.
    assert isinstance(cache_manager.get(key, repo_root=repo_root), cache_manager.Miss)

    result = generator.generate(
        bundle, MODEL, list(RETRY_FEEDBACK), repo_root=repo_root, llm_backend=backend
    )

    assert _call_count(log_path) == 1
    files = field(result, "files")
    assert files, "generate should return files for a complete reply"
    assert not field(result, "model_call_error")
    assert not field(result, "refused")
    assert field(result, "cache_hit") is False

    # generate() itself MUST NOT write the cache.
    assert isinstance(cache_manager.get(key, repo_root=repo_root), cache_manager.Miss)
    assert _entry_count(cache_manager, repo_root) == 0

    # commit_cache writes it under the R-GEN-005 key.
    generator.commit_cache(result, repo_root)

    hit = cache_manager.get(key, repo_root=repo_root)
    assert not isinstance(hit, cache_manager.Miss)
    assert field(hit, "gate_type") == "generator"
    payload = field(hit, "payload")
    assert field(payload, "files") == dict(files)

    # A second generate with the same inputs is a cache hit; model never called.
    second = generator.generate(
        bundle, MODEL, list(RETRY_FEEDBACK), repo_root=repo_root, llm_backend=backend
    )
    assert _call_count(log_path) == 1, "a cache hit must never call the model"
    assert field(second, "cache_hit") is True
    assert dict(field(second, "files")) == dict(files)


def test_commit_cache_writes_nothing_for_model_call_error(env):
    repo_root, log_path = env
    cache_manager = _load_cache_manager()
    bundle = _make_bundle()
    backend = _make_backend(log_path, mode="error")
    key = _cache_key(cache_manager, bundle, RETRY_FEEDBACK, MODEL)

    result = generator.generate(
        bundle, MODEL, list(RETRY_FEEDBACK), repo_root=repo_root, llm_backend=backend
    )
    assert _call_count(log_path) == 1
    assert field(result, "model_call_error")
    assert not field(result, "files")

    generator.commit_cache(result, repo_root)

    assert isinstance(cache_manager.get(key, repo_root=repo_root), cache_manager.Miss)
    assert _entry_count(cache_manager, repo_root) == 0