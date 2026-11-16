import generator

import hashlib
import importlib.util
import json
import re
import sys
from collections.abc import Mapping
from dataclasses import dataclass, field as dc_field
from pathlib import Path

import pytest


COMPONENT_ID = "comp-foo"
SLUG = "foo"
MODEL = "anthropic:claude-sonnet-5"
SPEC_BUNDLE_HASH = "sha256:" + hashlib.sha256(b"ac-gen-017 synthetic spec state").hexdigest()

CANDIDATE_CONTENT = "def foo(x):\n    return 2 * x\n"
HINT_CONTENT = "def foo(x):\n    # prior hint code\n    return x + x\n"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


@dataclass
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

    _FIELDS = (
        "component_id", "spec_bundle_hash", "spec", "interface", "constraints",
        "dependency_interfaces", "dependency_context", "dependency_usage",
        "vars", "glossary", "hint_code",
    )

    def __getitem__(self, key):
        if key not in self._FIELDS:
            raise KeyError(key)
        return getattr(self, key)

    def __iter__(self):
        return iter(self._FIELDS)

    def __len__(self):
        return len(self._FIELDS)


def make_bundle(hint_code):
    return FakeSpecBundle(
        component_id=COMPONENT_ID,
        spec_bundle_hash=SPEC_BUNDLE_HASH,
        spec="# Foo\n\n## Purpose\n\nFoo doubles a number.\n\n# R-FOO-001\n\n"
             "**R-FOO-001** — `foo(x)` MUST return `2 * x`.",
        interface="# Library\n\n```\nfoo(x: int) -> int\n```",
        constraints="# Constraints\n\nNone.",
        glossary="# Glossary\n\n- **Foo** — a test term.",
        hint_code=hint_code,
    )


def load_cache_manager():
    gen = next(p for p in Path(generator.__file__).resolve().parents if p.name == "gen")
    base = gen / "cache-manager"
    path = base / "cache_manager.py" if (base / "cache_manager.py").is_file() else base / "cache_manager" / "__init__.py"
    name = "_ac_gen_017_cache_manager"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def make_backend(log_path, content):
    def backend(prompt, model, **params):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"model": model}) + "\n")
        nonce = re.search(r"-----BEGIN FILE ([0-9a-f]{32}):", prompt).group(1)
        text = (
            f"-----BEGIN FILE {nonce}: foo.py-----\n"
            f"{content}"
            f"-----END FILE {nonce}-----\n"
            f"-----END REPLY {nonce}-----\n"
        )
        return {"text": text, "model": model, "backend": "mock", "model_call_error": None}
    return backend


def call_count(log_path):
    if not Path(log_path).exists():
        return 0
    return len([l for l in Path(log_path).read_text(encoding="utf-8").splitlines() if l.strip()])


def snapshot_gen(repo_root):
    gen = Path(repo_root) / "gen"
    snap = {}
    if not gen.exists():
        return snap
    for p in sorted(gen.rglob("*")):
        if "__pycache__" in p.parts:
            continue
        rel = p.relative_to(gen).as_posix()
        snap[rel] = p.read_bytes() if p.is_file() else None
    return snap


def gate_inputs_hash(retry_feedback=None):
    raw = json.dumps(sorted(retry_feedback or []), sort_keys=True).encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    monkeypatch.chdir(cwd)
    return repo_root, tmp_path


def test_hint_mode_miss_returns_candidate_without_writing_gen_or_cache(env):
    repo_root, tmp_path = env
    cache_manager = load_cache_manager()

    gen_dir = repo_root / "gen" / SLUG
    gen_dir.mkdir(parents=True)
    (gen_dir / "foo.py").write_text(HINT_CONTENT, encoding="utf-8")
    before = snapshot_gen(repo_root)

    stats_before = cache_manager.stats(repo_root=repo_root)
    assert field(stats_before, "entry_count") == 0

    log_path = tmp_path / "calls.log"
    bundle = make_bundle({"foo.py": HINT_CONTENT})
    result = generator.generate(
        bundle, MODEL, repo_root=repo_root,
        llm_backend=make_backend(log_path, CANDIDATE_CONTENT),
    )

    assert call_count(log_path) == 1
    assert field(result, "cache_hit") is False
    assert field(result, "model_call_error") is None
    assert field(result, "refused") is None
    files = field(result, "files")
    assert "foo.py" in files
    assert files["foo.py"].strip() == CANDIDATE_CONTENT.strip()

    # gen/<component>/ untouched
    assert snapshot_gen(repo_root) == before

    # nothing written to the cache
    stats_after = cache_manager.stats(repo_root=repo_root)
    assert field(stats_after, "entry_count") == 0
    key = cache_manager.CacheKey(
        spec_bundle_hash=SPEC_BUNDLE_HASH,
        gate_inputs_hash=gate_inputs_hash(None),
        gate_version=generator.GATE_VERSION,
        model_pin=MODEL,
    )
    assert isinstance(cache_manager.get(key, repo_root=repo_root), cache_manager.Miss)


def test_hint_mode_hit_returns_cached_cold_result_without_model_call_or_gen_write(env):
    repo_root, tmp_path = env
    cache_manager = load_cache_manager()

    # Produce and cache a cold-mode result for the exact same spec state.
    cold_log = tmp_path / "cold_calls.log"
    cold_result = generator.generate(
        make_bundle(None), MODEL, repo_root=repo_root,
        llm_backend=make_backend(cold_log, CANDIDATE_CONTENT),
    )
    assert call_count(cold_log) == 1
    cold_files = field(cold_result, "files")
    assert cold_files, "cold-mode setup produced no files"
    generator.commit_cache(cold_result, repo_root=repo_root)
    assert field(cache_manager.stats(repo_root=repo_root), "entry_count") >= 1

    # Hint code is the component's current gen/<component>/ content.
    gen_dir = repo_root / "gen" / SLUG
    hint_code = {}
    if gen_dir.exists():
        for p in gen_dir.rglob("*"):
            if p.is_file() and "__pycache__" not in p.parts:
                hint_code[p.relative_to(gen_dir).as_posix()] = p.read_text(encoding="utf-8")
    if not hint_code:
        hint_code = {"foo.py": HINT_CONTENT}
    before = snapshot_gen(repo_root)
    entries_before = field(cache_manager.stats(repo_root=repo_root), "entry_count")

    hint_log = tmp_path / "hint_calls.log"
    result = generator.generate(
        make_bundle(hint_code), MODEL, repo_root=repo_root,
        llm_backend=make_backend(hint_log, "def foo(x):\n    return 'should not be used'\n"),
    )

    # no model call occurs
    assert call_count(hint_log) == 0
    # the cached result is returned
    assert field(result, "cache_hit") is True
    assert field(result, "model_call_error") is None
    assert field(result, "refused") is None
    assert dict(field(result, "files")) == dict(cold_files)
    # gen/<component>/ stays untouched
    assert snapshot_gen(repo_root) == before
    assert field(cache_manager.stats(repo_root=repo_root), "entry_count") == entries_before