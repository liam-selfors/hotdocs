# hotdocs-criterion: sha256:9f99408c3b7715cf4013bfacf8a8b4258de6d545002863b46de79b844e3d804d
import hashlib
import importlib.util
import json
import re
import sys
from collections.abc import Mapping
from pathlib import Path

import pytest

import generator


MODEL = "claude-sonnet-5"
COMPONENT_ID = "comp-foo"
SLUG = "foo"
SPEC_BUNDLE_HASH = "sha256:" + hashlib.sha256(b"ac-gen-017-spec-state").hexdigest()

OLD_HINT_CONTENT = "def foo(x):\n    return x + x  # old hint code\n"
COLD_CONTENT = "def foo(x):\n    return 2 * x  # cold candidate\n"
HINT_CONTENT = "def foo(x):\n    return 2 * x  # hint candidate\n"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def load_module(path, module_name):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def load_cache_manager():
    gen = next(p for p in Path(generator.__file__).resolve().parents if p.name == "gen")
    base = gen / "cache-manager"
    flat = base / "cache_manager.py"
    path = flat if flat.is_file() else base / "cache_manager" / "__init__.py"
    return load_module(path, "cache_manager")


class FakeBundle(Mapping):
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

    def __init__(self, **kw):
        self.component_id = kw["component_id"]
        self.spec_bundle_hash = kw["spec_bundle_hash"]
        self.spec = kw.get("spec", "")
        self.interface = kw.get("interface", "")
        self.constraints = kw.get("constraints", "")
        self.dependency_interfaces = kw.get("dependency_interfaces", {})
        self.dependency_context = kw.get("dependency_context", {})
        self.dependency_usage = kw.get("dependency_usage", {})
        self.vars = kw.get("vars", {})
        self.glossary = kw.get("glossary", "")
        self.hint_code = kw.get("hint_code", None)

    def __getitem__(self, key):
        if key not in self._FIELDS:
            raise KeyError(key)
        return getattr(self, key)

    def __iter__(self):
        return iter(self._FIELDS)

    def __len__(self):
        return len(self._FIELDS)


def make_bundle(hint_code):
    return FakeBundle(
        component_id=COMPONENT_ID,
        spec_bundle_hash=SPEC_BUNDLE_HASH,
        spec="# Foo\n\n## Purpose\n\nFoo doubles a number.\n\n"
        "# R-FOO-001\n\n**R-FOO-001** — `foo(x)` MUST return `2 * x`.",
        interface="# Library\n\n```\nfoo(x: int) -> int\n```",
        constraints="# Constraints\n\nNone.",
        glossary="# Glossary\n\n- **Foo** — a test term.",
        hint_code=hint_code,
    )


def make_backend(log_path, content):
    def backend(prompt, model, **params):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write("call " + model + "\n")
        nonce = re.search(r"-----BEGIN FILE ([0-9a-f]{32}):", prompt).group(1)
        text = (
            "-----BEGIN FILE " + nonce + ": foo.py-----\n"
            + content
            + "-----END FILE " + nonce + "-----\n"
            + "-----END REPLY " + nonce + "-----\n"
        )
        return {"text": text, "model": model, "backend": "mock", "model_call_error": None}

    return backend


def call_count(log_path):
    if not log_path.exists():
        return 0
    return len([ln for ln in log_path.read_text(encoding="utf-8").splitlines() if ln.strip()])


def snapshot(directory):
    if not directory.exists():
        return None
    return {
        str(p.relative_to(directory)): p.read_bytes()
        for p in sorted(directory.rglob("*"))
        if p.is_file()
    }


def cache_key(cache_manager):
    gate_inputs_hash = "sha256:" + hashlib.sha256(
        json.dumps(sorted([]), sort_keys=True).encode("utf-8")
    ).hexdigest()
    return cache_manager.CacheKey(
        spec_bundle_hash=SPEC_BUNDLE_HASH,
        gate_inputs_hash=gate_inputs_hash,
        gate_version=generator.GATE_VERSION,
        model_pin=MODEL,
    )


@pytest.fixture
def repo_root(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    root = tmp_path / "repo"
    root.mkdir()
    monkeypatch.chdir(root)
    return root


def test_hint_mode_miss_returns_candidate_without_writing_gen_or_cache(repo_root, tmp_path):
    cache_manager = load_cache_manager()
    gen_dir = repo_root / "gen" / SLUG
    gen_dir.mkdir(parents=True)
    (gen_dir / "foo.py").write_text(OLD_HINT_CONTENT, encoding="utf-8")
    before = snapshot(gen_dir)

    key = cache_key(cache_manager)
    assert isinstance(cache_manager.get(key, repo_root=repo_root), cache_manager.Miss)
    assert cache_manager.stats(repo_root=repo_root)["entry_count"] == 0

    log_path = tmp_path / "hint_model_calls.log"
    bundle = make_bundle({"foo.py": OLD_HINT_CONTENT})
    result = generator.generate(
        bundle, MODEL, repo_root=repo_root, llm_backend=make_backend(log_path, HINT_CONTENT)
    )

    assert call_count(log_path) == 1
    assert field(result, "cache_hit") is False
    assert field(result, "model_call_error") is None
    assert field(result, "refused") is None
    files = field(result, "files")
    assert "foo.py" in files
    assert files["foo.py"].rstrip("\n") == HINT_CONTENT.rstrip("\n")

    # gen/<component>/ untouched
    assert snapshot(gen_dir) == before

    # nothing written to the cache by generate
    assert isinstance(cache_manager.get(key, repo_root=repo_root), cache_manager.Miss)
    assert cache_manager.stats(repo_root=repo_root)["entry_count"] == 0

    # commit_cache must not write a hint-mode result either
    generator.commit_cache(result, repo_root=repo_root)
    assert isinstance(cache_manager.get(key, repo_root=repo_root), cache_manager.Miss)
    assert cache_manager.stats(repo_root=repo_root)["entry_count"] == 0
    assert snapshot(gen_dir) == before


def test_hint_mode_hit_returns_cached_cold_result_without_model_call(repo_root, tmp_path):
    cache_manager = load_cache_manager()
    key = cache_key(cache_manager)

    # Produce and cache a cold-mode result for this exact spec state.
    cold_log = tmp_path / "cold_model_calls.log"
    cold_result = generator.generate(
        make_bundle(None), MODEL, repo_root=repo_root, llm_backend=make_backend(cold_log, COLD_CONTENT)
    )
    assert call_count(cold_log) == 1
    cold_files = field(cold_result, "files")
    assert "foo.py" in cold_files
    generator.commit_cache(cold_result, repo_root=repo_root)
    assert not isinstance(cache_manager.get(key, repo_root=repo_root), cache_manager.Miss)

    gen_dir = repo_root / "gen" / SLUG
    before = snapshot(gen_dir)
    hint_code = dict(before_text) if (before_text := {
        k: v.decode("utf-8") for k, v in (before or {}).items()
    }) else {"foo.py": OLD_HINT_CONTENT}

    hint_log = tmp_path / "hint_model_calls.log"
    result = generator.generate(
        make_bundle(hint_code), MODEL, repo_root=repo_root,
        llm_backend=make_backend(hint_log, HINT_CONTENT),
    )

    # no model call occurs
    assert call_count(hint_log) == 0
    # the cached result is returned
    assert field(result, "cache_hit") is True
    assert field(result, "model_call_error") is None
    assert field(result, "refused") is None
    assert field(result, "files") == cold_files
    # gen/<component>/ stays untouched
    assert snapshot(gen_dir) == before