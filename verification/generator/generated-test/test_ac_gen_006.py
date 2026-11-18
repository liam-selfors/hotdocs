# hotdocs-criterion: sha256:a18f47514303ab8bd2aeb113f087d57e68d577676c31d5daa32ae8bb1a78e5d8
import hashlib
import importlib.util
import json
import re
import sys
from dataclasses import dataclass, field as dc_field
from pathlib import Path

import pytest

import generator


def load_module(path, module_name):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _load_cache_manager():
    gen = next(
        (p for p in Path(generator.__file__).resolve().parents if p.name == "gen"),
        None,
    )
    assert gen is not None, "could not locate the tool's gen/ directory"
    base = gen / "cache-manager"
    flat = base / "cache_manager.py"
    path = flat if flat.is_file() else base / "cache_manager" / "__init__.py"
    return load_module(path, "cache_manager")


@dataclass
class FakeSpecBundle:
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
        return getattr(self, key)

    def get(self, key, default=None):
        return getattr(self, key, default)

    def keys(self):
        return list(self.__dataclass_fields__.keys())

    def __contains__(self, key):
        return key in self.__dataclass_fields__

    def __iter__(self):
        return iter(self.keys())


def _bundle(seed):
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    return FakeSpecBundle(
        component_id="comp-foo",
        spec_bundle_hash="sha256:" + digest,
        spec="# Foo\n\nFoo doubles a number.\n\n**R-FOO-001** — `foo(x)` MUST return `2 * x`.",
        interface="# Library\n\n```\nfoo(x: int) -> int\n```",
        constraints="# Constraints\n\nNone.",
        glossary="# Glossary\n\n- **Foo** — a test term.",
    )


FILE_CONTENT = "def foo(x):\n    return 2 * x\n"


def _good_backend(calls):
    def backend(prompt, model, **params):
        calls.append(model)
        nonce = re.search(r"-----BEGIN FILE ([0-9a-f]{32}):", prompt).group(1)
        text = (
            "Here is the code.\n"
            + "-----BEGIN FILE " + nonce + ": foo.py-----\n"
            + FILE_CONTENT
            + "-----END FILE " + nonce + "-----\n"
            + "-----END REPLY " + nonce + "-----\n"
        )
        return {"text": text, "model": model, "backend": "mock", "model_call_error": None}

    return backend


def _error_backend(calls):
    def backend(prompt, model, **params):
        calls.append(model)
        return {
            "text": None,
            "model": model,
            "backend": "mock",
            "model_call_error": {"category": "network", "message": "backend unreachable"},
        }

    return backend


def _key(cm, bundle_hash, retry_feedback, model):
    gate_inputs_hash = "sha256:" + hashlib.sha256(
        json.dumps(sorted(retry_feedback or []), sort_keys=True).encode("utf-8")
    ).hexdigest()
    return cm.CacheKey(
        spec_bundle_hash=bundle_hash,
        gate_inputs_hash=gate_inputs_hash,
        gate_version=generator.GATE_VERSION,
        model_pin=model,
    )


@pytest.fixture(autouse=True)
def _no_remote_store(monkeypatch, tmp_path):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    monkeypatch.chdir(tmp_path)


def test_generate_does_not_write_cache_and_commit_cache_does(tmp_path):
    cm = _load_cache_manager()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    model = "claude-sonnet-5"
    retry_feedback = ["R-FOO-002", "R-FOO-001"]
    bundle = _bundle("ac-gen-006-success")
    key = _key(cm, bundle.spec_bundle_hash, retry_feedback, model)

    # Empty cache to start.
    assert isinstance(cm.get(key, repo_root=repo_root), cm.Miss)
    assert cm.stats(repo_root=repo_root)["entry_count"] == 0

    calls = []
    result = generator.generate(
        bundle, model, retry_feedback,
        repo_root=repo_root, llm_backend=_good_backend(calls),
    )

    assert len(calls) == 1
    files = field(result, "files")
    assert files, "expected a result with files"
    assert field(result, "model_call_error") is None
    assert field(result, "refused") is None
    assert field(result, "cache_hit") is False

    # generate() itself MUST NOT write to cache-manager.
    assert isinstance(cm.get(key, repo_root=repo_root), cm.Miss)
    assert cm.stats(repo_root=repo_root)["entry_count"] == 0

    # commit_cache writes under the R-GEN-005 key.
    generator.commit_cache(result, repo_root)

    stored = cm.get(key, repo_root=repo_root)
    assert not isinstance(stored, cm.Miss)
    assert field(stored, "gate_type") == "generator"
    payload = field(stored, "payload")
    assert field(payload, "files") == files

    # A second generate with the same inputs is a cache hit, model never called.
    calls2 = []
    result2 = generator.generate(
        bundle, model, retry_feedback,
        repo_root=repo_root, llm_backend=_good_backend(calls2),
    )
    assert calls2 == []
    assert field(result2, "cache_hit") is True
    assert field(result2, "files") == files
    assert field(result2, "model_call_error") is None
    assert field(result2, "refused") is None


def test_commit_cache_writes_nothing_for_model_call_error(tmp_path):
    cm = _load_cache_manager()
    repo_root = tmp_path / "repo-err"
    repo_root.mkdir()

    model = "claude-sonnet-5"
    retry_feedback = ["R-FOO-001"]
    bundle = _bundle("ac-gen-006-error")
    key = _key(cm, bundle.spec_bundle_hash, retry_feedback, model)

    assert isinstance(cm.get(key, repo_root=repo_root), cm.Miss)
    assert cm.stats(repo_root=repo_root)["entry_count"] == 0

    calls = []
    result = generator.generate(
        bundle, model, retry_feedback,
        repo_root=repo_root, llm_backend=_error_backend(calls),
    )
    assert len(calls) == 1
    assert field(result, "model_call_error") is not None
    assert not field(result, "files")
    assert field(result, "cache_hit") is False

    generator.commit_cache(result, repo_root)

    assert isinstance(cm.get(key, repo_root=repo_root), cm.Miss)
    assert cm.stats(repo_root=repo_root)["entry_count"] == 0