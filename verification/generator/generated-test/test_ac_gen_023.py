"""AC-GEN-023 (Covers R-GEN-021): generate() rejects an incomplete reply
before writing or caching anything."""

import generator

import hashlib
import importlib.util
import json
import re
import sys
import uuid
from dataclasses import dataclass, field as dc_field
from pathlib import Path

import pytest


MODEL = "anthropic:claude-sonnet-5"
COMPONENT_ID = "comp-widget-maker"
SLUG = "widget-maker"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


@dataclass
class _Bundle:
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
    hint_code: dict | None = None

    def __getitem__(self, key):
        if key not in self.__dataclass_fields__:
            raise KeyError(key)
        return getattr(self, key)

    def get(self, key, default=None):
        if key in self.__dataclass_fields__:
            return getattr(self, key)
        return default

    def __contains__(self, key):
        return key in self.__dataclass_fields__

    def keys(self):
        return list(self.__dataclass_fields__)

    def items(self):
        return [(k, getattr(self, k)) for k in self.__dataclass_fields__]

    def values(self):
        return [getattr(self, k) for k in self.__dataclass_fields__]


def _make_bundle():
    return _Bundle(
        component_id=COMPONENT_ID,
        spec_bundle_hash="sha256:" + hashlib.sha256(uuid.uuid4().hex.encode()).hexdigest(),
        spec=(
            "# Widget Maker\n\n## Purpose\n\nWidget Maker makes widgets.\n\n"
            "# R-WIDGET-001\n\n**R-WIDGET-001** — `make()` MUST return `1`."
        ),
        interface="# Library\n\n```\nmake() -> int\n```",
        constraints="None.",
        glossary="- **Widget** — a test term.",
        hint_code=None,
    )


def _tool_root():
    for p in Path(generator.__file__).resolve().parents:
        if p.name == "gen":
            return p.parent
    return None


def _load_cache_manager():
    root = _tool_root()
    if root is None:
        return None
    base = root / "gen" / "cache-manager"
    path = base / "cache_manager.py"
    if not path.is_file():
        path = base / "cache_manager" / "__init__.py"
    if not path.is_file():
        return None
    name = "_ac_gen_023_cache_manager"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(name, None)
        return None
    return module


def _nonce(prompt):
    return re.search(r"-----BEGIN FILE ([0-9a-f]{32}):", prompt).group(1)


def _block(nonce, path, content):
    return (
        f"-----BEGIN FILE {nonce}: {path}-----\n"
        f"{content}"
        f"-----END FILE {nonce}-----\n"
    )


def _open_block(nonce, path, content):
    return f"-----BEGIN FILE {nonce}: {path}-----\n{content}"


def _end(nonce):
    return f"-----END REPLY {nonce}-----\n"


WIDGET_SRC = "def make():\n    return 1\n"
HELPERS_SRC = "def helper():\n    return 2\n"


def _backend(log_path, build_reply):
    def backend(prompt, model, **params):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"model": model}) + "\n")
        try:
            nonce = _nonce(prompt)
        except AttributeError:
            nonce = "0" * 32
        return {
            "text": build_reply(nonce),
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    return backend


@pytest.fixture
def env(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    work = tmp_path / "cwd"
    work.mkdir()
    monkeypatch.chdir(work)
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    return repo_root, tmp_path / "calls.log"


def _run(repo_root, log_path, build_reply):
    bundle = _make_bundle()
    result = generator.generate(
        bundle, MODEL, repo_root=repo_root, llm_backend=_backend(log_path, build_reply)
    )
    assert log_path.is_file() and log_path.read_text().strip(), "mock model was never called"
    return bundle, result


def _error(result):
    err = field(result, "model_call_error")
    assert err is not None, "expected a model_call_error"
    return err


def _assert_nothing_cached(repo_root, bundle):
    cache_dir = repo_root / ".hotdocs" / "cache"
    if cache_dir.exists():
        assert not [p for p in cache_dir.rglob("*") if p.is_file()], "cache store holds entries"
    cm = _load_cache_manager()
    if cm is not None:
        gate_inputs_hash = "sha256:" + hashlib.sha256(
            json.dumps(sorted([]), sort_keys=True).encode("utf-8")
        ).hexdigest()
        key = cm.CacheKey(
            spec_bundle_hash=bundle.spec_bundle_hash,
            gate_inputs_hash=gate_inputs_hash,
            gate_version=generator.GATE_VERSION,
            model_pin=MODEL,
        )
        assert isinstance(cm.get(key, repo_root=repo_root), cm.Miss)
        stats = cm.stats(repo_root=repo_root)
        assert field(stats, "entry_count") == 0


def test_complete_block_without_end_reply_is_truncated(env):
    repo_root, log = env
    bundle, result = _run(repo_root, log, lambda n: _block(n, "widget_maker.py", WIDGET_SRC))
    err = _error(result)
    assert field(err, "category") == "truncated_response"
    assert not field(result, "files")
    assert field(result, "cache_hit") is False
    assert not (repo_root / "gen" / SLUG).exists()
    _assert_nothing_cached(repo_root, bundle)


def test_unclosed_file_block_with_end_reply_names_file(env):
    repo_root, log = env
    _, result = _run(
        repo_root,
        log,
        lambda n: _block(n, "widget_maker.py", WIDGET_SRC)
        + _open_block(n, "helpers.py", HELPERS_SRC)
        + _end(n),
    )
    err = _error(result)
    assert field(err, "category") == "truncated_response"
    assert "helpers.py" in field(err, "message")
    assert not field(result, "files")
    assert not (repo_root / "gen" / SLUG).exists()


def test_unclosed_file_block_without_end_reply_names_file(env):
    repo_root, log = env
    _, result = _run(
        repo_root,
        log,
        lambda n: _block(n, "widget_maker.py", WIDGET_SRC)
        + _open_block(n, "helpers.py", HELPERS_SRC),
    )
    err = _error(result)
    assert field(err, "category") == "truncated_response"
    assert "helpers.py" in field(err, "message")
    assert not field(result, "files")
    assert not (repo_root / "gen" / SLUG).exists()


def test_prose_only_reply_is_empty_response(env):
    repo_root, log = env
    _, result = _run(repo_root, log, lambda n: "I cannot help with that.")
    err = _error(result)
    assert field(err, "category") == "empty_response"
    assert not field(result, "files")
    assert not (repo_root / "gen" / SLUG).exists()


def test_reply_without_module_file_is_missing_module(env):
    repo_root, log = env
    bundle, result = _run(
        repo_root, log, lambda n: _block(n, "notes.py", "NOTES = 1\n") + _end(n)
    )
    err = _error(result)
    assert field(err, "category") == "missing_module"
    assert not field(result, "files")
    assert field(result, "cache_hit") is False
    assert not (repo_root / "gen" / SLUG).exists()
    _assert_nothing_cached(repo_root, bundle)


def test_package_layout_is_accepted_and_written(env):
    repo_root, log = env
    init_src = "from .core import make\n"
    _, result = _run(
        repo_root,
        log,
        lambda n: _block(n, "widget_maker/__init__.py", init_src)
        + _block(n, "widget_maker/core.py", WIDGET_SRC)
        + _end(n),
    )
    assert field(result, "model_call_error") is None
    files = field(result, "files")
    assert "widget_maker/__init__.py" in files
    assert "widget_maker/core.py" in files
    out = repo_root / "gen" / SLUG
    assert (out / "widget_maker" / "__init__.py").is_file()
    assert (out / "widget_maker" / "core.py").is_file()
    assert "from .core import make" in (out / "widget_maker" / "__init__.py").read_text()
    assert "def make" in (out / "widget_maker" / "core.py").read_text()