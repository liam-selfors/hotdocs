import generator

import dataclasses
import hashlib
import importlib.util
import json
import re
import sys
import urllib.error
from collections.abc import Mapping
from pathlib import Path

import pytest


MODEL = "anthropic:claude-sonnet-5"
COMPONENT_ID = "comp-foo"
SLUG = "foo"
BUNDLE_HASH = "sha256:" + hashlib.sha256(b"ac-gen-008-bundle").hexdigest()


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


@dataclasses.dataclass
class _SpecBundle(Mapping):
    """A SpecBundle-shaped value: the documented fields in order, also
    readable as a read-only mapping (bundle["spec"], bundle.get("spec"))."""

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

    def __getitem__(self, key):
        names = [f.name for f in dataclasses.fields(self)]
        if key not in names:
            raise KeyError(key)
        return getattr(self, key)

    def __iter__(self):
        return iter([f.name for f in dataclasses.fields(self)])

    def __len__(self):
        return len(dataclasses.fields(self))


def _make_bundle():
    return _SpecBundle(
        component_id=COMPONENT_ID,
        spec_bundle_hash=BUNDLE_HASH,
        spec=(
            "# Foo\n\n## Purpose\n\nFoo doubles a number.\n\n"
            "# R-FOO-001\n\n**R-FOO-001** \u2014 `foo(x)` MUST return `2 * x`."
        ),
        interface="# Library\n\n```\nfoo(x: int) -> int\n```",
        constraints="None.",
        dependency_interfaces={},
        dependency_context={},
        dependency_usage={},
        vars={},
        glossary="# Glossary\n\n- **Foo** \u2014 a test term.",
        hint_code=None,
    )


def _tool_gen_dir():
    return next(
        p for p in Path(generator.__file__).resolve().parents if p.name == "gen"
    )


def _load_cache_manager():
    if "cache_manager" in sys.modules and hasattr(sys.modules["cache_manager"], "stats"):
        return sys.modules["cache_manager"]
    base = _tool_gen_dir() / "cache-manager"
    path = (
        base / "cache_manager.py"
        if (base / "cache_manager.py").is_file()
        else base / "cache_manager" / "__init__.py"
    )
    spec = importlib.util.spec_from_file_location("cache_manager", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["cache_manager"] = module
    spec.loader.exec_module(module)
    return module


def _cache_key(cache_manager):
    gate_inputs_hash = "sha256:" + hashlib.sha256(
        json.dumps(sorted([]), sort_keys=True).encode("utf-8")
    ).hexdigest()
    return cache_manager.CacheKey(
        spec_bundle_hash=BUNDLE_HASH,
        gate_inputs_hash=gate_inputs_hash,
        gate_version=generator.GATE_VERSION,
        model_pin=MODEL,
    )


def _entry_count(cache_manager, repo_root):
    stats = cache_manager.stats(repo_root=repo_root)
    return stats["entry_count"] if isinstance(stats, dict) else getattr(stats, "entry_count")


@pytest.fixture
def env(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    monkeypatch.chdir(cwd)
    return repo_root, tmp_path


def _gen_files(repo_root):
    gen_dir = repo_root / "gen" / SLUG
    if not gen_dir.exists():
        return []
    return [p for p in gen_dir.rglob("*") if p.is_file()]


def test_network_error_is_model_call_error_not_cache_hit(env):
    repo_root, tmp_path = env
    log_path = tmp_path / "mock_calls.log"

    def failing_backend(prompt, model, **params):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"model": model}) + "\n")
        raise urllib.error.URLError("connection refused")

    result = generator.generate(
        _make_bundle(), MODEL, repo_root=repo_root, llm_backend=failing_backend
    )

    # The model call was actually attempted.
    assert log_path.is_file()
    assert log_path.read_text(encoding="utf-8").strip() != ""

    error = field(result, "model_call_error")
    assert error is not None
    assert field(result, "files") == {}
    assert field(result, "cache_hit") is False
    assert field(result, "refused") is None


def test_reply_without_file_blocks_is_empty_response(env):
    repo_root, tmp_path = env
    cache_manager = _load_cache_manager()
    key = _cache_key(cache_manager)
    assert isinstance(cache_manager.get(key, repo_root=repo_root), cache_manager.Miss)
    count_before = _entry_count(cache_manager, repo_root)
    log_path = tmp_path / "mock_calls.log"

    def empty_backend(prompt, model, **params):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"model": model}) + "\n")
        match = re.search(r"-----BEGIN FILE ([0-9a-f]{32}):", prompt)
        text = "I have considered the spec but produced no files.\n"
        if match:
            text += "-----END REPLY " + match.group(1) + "-----\n"
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    result = generator.generate(
        _make_bundle(), MODEL, repo_root=repo_root, llm_backend=empty_backend
    )

    assert log_path.is_file()
    assert log_path.read_text(encoding="utf-8").strip() != ""

    error = field(result, "model_call_error")
    assert error is not None
    category = error["category"] if isinstance(error, dict) else getattr(error, "category")
    assert category == "empty_response"
    assert field(result, "files") == {}
    assert field(result, "cache_hit") is False
    assert field(result, "refused") is None

    # Nothing written to gen/<component>/.
    assert _gen_files(repo_root) == []

    # Nothing cached.
    assert isinstance(cache_manager.get(key, repo_root=repo_root), cache_manager.Miss)
    assert _entry_count(cache_manager, repo_root) == count_before