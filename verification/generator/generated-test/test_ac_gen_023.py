# hotdocs-criterion: sha256:2ebc27a98e9e992218f5a5bdbf71e629679d12755d633b295abe67ae32c9f734
import importlib.util
import re
import sys
from pathlib import Path

import pytest

import generator


COMPONENT_ID = "comp-widget-maker"
SLUG = "widget-maker"
MODEL = "claude-sonnet-5"


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


class Bundle(dict):
    """A SpecBundle stand-in readable both as a mapping and by attribute."""

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)


def make_bundle():
    return Bundle(
        component_id=COMPONENT_ID,
        spec_bundle_hash="sha256:" + "a1" * 32,
        spec="# Widget Maker\n\nWidget maker makes widgets.",
        interface="# Library\n\n```\nmake_widget() -> dict\n```",
        constraints="# Constraints\n\nNone.",
        dependency_interfaces={},
        dependency_context={},
        dependency_usage={},
        vars={},
        glossary="# Glossary\n\n- **Widget** — a test term.",
        hint_code=None,
    )


def nonce_of(prompt):
    return re.search(r"-----BEGIN FILE ([0-9a-f]{32}):", prompt).group(1)


def block(nonce, path, content):
    return (
        "-----BEGIN FILE " + nonce + ": " + path + "-----\n"
        + content + "\n"
        + "-----END FILE " + nonce + "-----\n"
    )


def end_reply(nonce):
    return "-----END REPLY " + nonce + "-----\n"


def make_backend(build_reply, calls):
    def backend(prompt, model, **params):
        calls.append(prompt)
        nonce = nonce_of(prompt)
        return {
            "text": build_reply(nonce),
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    return backend


def run(tmp_path, build_reply):
    calls = []
    result = generator.generate(
        make_bundle(),
        MODEL,
        repo_root=tmp_path,
        llm_backend=make_backend(build_reply, calls),
    )
    assert len(calls) == 1, "mock model was not called exactly once"
    return result


def assert_nothing_cached(tmp_path):
    cache_manager = load_cache_manager()
    stats = cache_manager.stats(repo_root=tmp_path)
    assert field(stats, "entry_count") == 0


def assert_nothing_written(tmp_path):
    assert not (tmp_path / "gen" / SLUG).exists()


@pytest.fixture(autouse=True)
def _no_remote_cache(monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)


def test_complete_block_without_end_reply_is_truncated(tmp_path):
    def reply(nonce):
        return "Here is the code.\n" + block(nonce, "widget_maker.py", "def make_widget():\n    return {}\n")

    result = run(tmp_path, reply)
    err = field(result, "model_call_error")
    assert err is not None
    assert field(err, "category") == "truncated_response"
    assert field(result, "files") == {}
    assert field(result, "cache_hit") is False
    assert_nothing_written(tmp_path)
    assert_nothing_cached(tmp_path)


def test_unterminated_file_block_with_end_reply_names_file(tmp_path):
    def reply(nonce):
        return (
            block(nonce, "widget_maker.py", "def make_widget():\n    return {}\n")
            + "-----BEGIN FILE " + nonce + ": helpers.py-----\n"
            + "def helper():\n    return 1\n"
            + end_reply(nonce)
        )

    result = run(tmp_path, reply)
    err = field(result, "model_call_error")
    assert err is not None
    assert field(err, "category") == "truncated_response"
    assert "helpers.py" in field(err, "message")
    assert field(result, "files") == {}
    assert_nothing_written(tmp_path)
    assert_nothing_cached(tmp_path)


def test_unterminated_file_block_without_end_reply_names_file(tmp_path):
    def reply(nonce):
        return (
            block(nonce, "widget_maker.py", "def make_widget():\n    return {}\n")
            + "-----BEGIN FILE " + nonce + ": helpers.py-----\n"
            + "def helper():\n    return 1\n"
        )

    result = run(tmp_path, reply)
    err = field(result, "model_call_error")
    assert err is not None
    assert field(err, "category") == "truncated_response"
    assert "helpers.py" in field(err, "message")
    assert field(result, "files") == {}
    assert_nothing_written(tmp_path)
    assert_nothing_cached(tmp_path)


def test_reply_with_no_file_block_is_empty_response(tmp_path):
    def reply(nonce):
        return "I cannot help with that."

    result = run(tmp_path, reply)
    err = field(result, "model_call_error")
    assert err is not None
    assert field(err, "category") == "empty_response"
    assert field(result, "files") == {}
    assert_nothing_written(tmp_path)
    assert_nothing_cached(tmp_path)


def test_reply_without_module_file_is_missing_module(tmp_path):
    def reply(nonce):
        return block(nonce, "notes.py", "NOTES = 'just notes'\n") + end_reply(nonce)

    result = run(tmp_path, reply)
    err = field(result, "model_call_error")
    assert err is not None
    assert field(err, "category") == "missing_module"
    assert field(result, "files") == {}
    assert field(result, "cache_hit") is False
    assert_nothing_written(tmp_path)
    assert_nothing_cached(tmp_path)


def test_package_shaped_reply_is_accepted_and_written(tmp_path):
    init_src = "from .core import make_widget\n"
    core_src = "def make_widget():\n    return {}\n"

    def reply(nonce):
        return (
            "Here you go.\n"
            + block(nonce, "widget_maker/__init__.py", init_src)
            + block(nonce, "widget_maker/core.py", core_src)
            + end_reply(nonce)
        )

    result = run(tmp_path, reply)
    assert field(result, "model_call_error") is None
    assert field(result, "refused") is None
    files = field(result, "files")
    assert "widget_maker/__init__.py" in files
    assert "widget_maker/core.py" in files

    out = tmp_path / "gen" / SLUG
    init_path = out / "widget_maker" / "__init__.py"
    core_path = out / "widget_maker" / "core.py"
    assert init_path.is_file()
    assert core_path.is_file()
    assert "from .core import make_widget" in init_path.read_text(encoding="utf-8")
    assert "def make_widget" in core_path.read_text(encoding="utf-8")