# hotdocs-criterion: sha256:918ff7ee7bcb6ce21b67d39d32c31c0c4cace54fccc0bc2a54c61092d00432f7
import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest

import generator


MODEL = "claude-sonnet-5"
COMPONENT_ID = "comp-widget-maker"
SLUG = "widget-maker"


FAKE_PYTHON_ADAPTER = (
    "from pathlib import Path\n"
    "\n"
    "KIND = \"python\"\n"
    "\n"
    "\n"
    "def layout_errors(code_dir):\n"
    "    return [\"bad.py:1: SyntaxError: x\"] if (Path(code_dir) / \"bad.py\").exists() else []\n"
    "\n"
    "\n"
    "def provision(repo_root):\n"
    "    return {\"ok\": True, \"reason\": \"\", \"versions\": {\"python\": \"3.12\"}, "
    "\"lockfile_sha256\": None, \"interpreter\": \"/fake/python\"}\n"
)

COMPONENT_MD = (
    "---\n"
    "id: comp-widget-maker\n"
    "title: Widget Maker\n"
    "status: draft\n"
    "owners: [pipeline-team]\n"
    "depends_on: []\n"
    "sealed: false\n"
    "---\n"
    "\n"
    "# Widget Maker\n"
)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def load_module(path, module_name):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


class Bundle(dict):
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)


def make_bundle():
    return Bundle(
        component_id=COMPONENT_ID,
        spec_bundle_hash="sha256:" + hashlib.sha256(b"widget-maker-ac-gen-023").hexdigest(),
        spec="# Widget Maker\n\nMakes widgets.",
        interface="# Library\n\nmake() -> str",
        constraints="",
        dependency_interfaces={},
        dependency_context={},
        dependency_usage={},
        vars={},
        glossary="",
        hint_code=None,
    )


@pytest.fixture
def repo_root(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    root = tmp_path / "repo"
    root.mkdir()
    adapter = root / "gen" / "kind-python" / "kind_python.py"
    adapter.parent.mkdir(parents=True)
    adapter.write_text(FAKE_PYTHON_ADAPTER, encoding="utf-8")
    comp = root / "specs" / "components" / SLUG / "component.md"
    comp.parent.mkdir(parents=True)
    comp.write_text(COMPONENT_MD, encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    return root


def begin(nonce, path):
    return "-----BEGIN FILE " + nonce + ": " + path + "-----\n"


def end_file(nonce):
    return "-----END FILE " + nonce + "-----\n"


def end_reply(nonce):
    return "-----END REPLY " + nonce + "-----\n"


def block(nonce, path, content):
    return begin(nonce, path) + content + end_file(nonce)


def make_backend(build_reply):
    def backend(prompt, model, **params):
        m = re.search(r"-----BEGIN FILE ([0-9a-f]{32}):", prompt)
        nonce = m.group(1)
        return {
            "text": build_reply(nonce),
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }
    return backend


def load_cache_manager():
    gen = next(p for p in Path(generator.__file__).resolve().parents if p.name == "gen")
    base = gen / "cache-manager"
    path = base / "cache_manager.py" if (base / "cache_manager.py").is_file() else base / "cache_manager" / "__init__.py"
    return load_module(path, "cache_manager")


def assert_nothing_cached(repo_root, bundle):
    cm = load_cache_manager()
    key = cm.CacheKey(
        spec_bundle_hash=bundle["spec_bundle_hash"],
        gate_inputs_hash="sha256:" + hashlib.sha256(
            json.dumps(sorted([]), sort_keys=True).encode("utf-8")
        ).hexdigest(),
        gate_version=generator.GATE_VERSION,
        model_pin=MODEL,
    )
    got = cm.get(key, repo_root=repo_root)
    assert isinstance(got, cm.Miss)
    stats = cm.stats(repo_root=repo_root)
    assert field(stats, "entry_count") == 0


def run(repo_root, build_reply):
    bundle = make_bundle()
    result = generator.generate(
        bundle, MODEL, repo_root=repo_root, llm_backend=make_backend(build_reply)
    )
    return bundle, result


def error_of(result):
    err = field(result, "model_call_error")
    assert err is not None
    return err


def test_complete_block_without_end_reply_is_truncated(repo_root):
    def reply(nonce):
        return "Here you go.\n" + block(nonce, "widget_maker.py", "def make():\n    return 'w'\n")

    bundle, result = run(repo_root, reply)
    err = error_of(result)
    assert field(err, "category") == "truncated_response"
    assert field(result, "files") == {}
    assert not (repo_root / "gen" / SLUG).exists()
    assert_nothing_cached(repo_root, bundle)


def test_unclosed_block_with_end_reply_names_file(repo_root):
    def reply(nonce):
        return (
            block(nonce, "widget_maker.py", "def make():\n    return 'w'\n")
            + begin(nonce, "helpers.py")
            + "def helper():\n    return 1\n"
            + end_reply(nonce)
        )

    bundle, result = run(repo_root, reply)
    err = error_of(result)
    assert field(err, "category") == "truncated_response"
    assert "helpers.py" in field(err, "message")
    assert field(result, "files") == {}
    assert not (repo_root / "gen" / SLUG).exists()


def test_unclosed_block_without_end_reply_names_file(repo_root):
    def reply(nonce):
        return (
            block(nonce, "widget_maker.py", "def make():\n    return 'w'\n")
            + begin(nonce, "helpers.py")
            + "def helper():\n    return 1\n"
        )

    bundle, result = run(repo_root, reply)
    err = error_of(result)
    assert field(err, "category") == "truncated_response"
    assert "helpers.py" in field(err, "message")
    assert field(result, "files") == {}


def test_reply_without_any_block_is_empty_response(repo_root):
    def reply(nonce):
        return "I cannot help with that."

    bundle, result = run(repo_root, reply)
    err = error_of(result)
    assert field(err, "category") == "empty_response"
    assert field(result, "files") == {}


def test_reply_without_module_is_missing_module(repo_root):
    def reply(nonce):
        return block(nonce, "notes.py", "NOTES = 1\n") + end_reply(nonce)

    bundle, result = run(repo_root, reply)
    err = error_of(result)
    assert field(err, "category") == "missing_module"
    assert field(result, "files") == {}
    assert not (repo_root / "gen" / SLUG).exists()
    assert_nothing_cached(repo_root, bundle)


def test_package_reply_is_accepted_and_written(repo_root):
    init_src = "from .core import make\n"
    core_src = "def make():\n    return 'w'\n"

    def reply(nonce):
        return (
            block(nonce, "widget_maker/__init__.py", init_src)
            + block(nonce, "widget_maker/core.py", core_src)
            + end_reply(nonce)
        )

    bundle, result = run(repo_root, reply)
    assert field(result, "model_call_error") is None
    out = repo_root / "gen" / SLUG
    init_path = out / "widget_maker" / "__init__.py"
    core_path = out / "widget_maker" / "core.py"
    assert init_path.is_file()
    assert core_path.is_file()
    assert init_path.read_text(encoding="utf-8") == init_src
    assert core_path.read_text(encoding="utf-8") == core_src