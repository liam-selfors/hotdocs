# hotdocs-criterion: sha256:7773e8e05f2a993091a252358ff89bdf665ad984accb6a0f35b9714782a7b200
import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest

import generator


MODEL = "claude-sonnet-5"

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

PYTHON_ADAPTER = '''from pathlib import Path

KIND = "python"


def layout_errors(code_dir):
    return ["bad.py:1: SyntaxError: x"] if (Path(code_dir) / "bad.py").exists() else []


def provision(repo_root):
    return {"ok": True, "reason": "", "versions": {"python": "3.12"}, "lockfile_sha256": None, "interpreter": "/fake/python"}
'''


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def load_module(path, module_name):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def load_cache_manager(repo_root):
    candidates = []
    local = Path(repo_root) / "gen" / "cache-manager"
    candidates.append(local)
    gen = next(p for p in Path(generator.__file__).resolve().parents if p.name == "gen")
    candidates.append(gen / "cache-manager")
    for base in candidates:
        flat = base / "cache_manager.py"
        pkg = base / "cache_manager" / "__init__.py"
        if flat.is_file():
            return load_module(flat, "cache_manager")
        if pkg.is_file():
            return load_module(pkg, "cache_manager")
    raise RuntimeError("cache_manager not found")


class Bundle(dict):
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)


def make_bundle():
    return Bundle(
        component_id="comp-widget-maker",
        spec_bundle_hash="sha256:" + hashlib.sha256(b"ac-gen-023-widget-maker").hexdigest(),
        spec="# Widget Maker\n\nMakes widgets.",
        interface="make_widget() -> str",
        constraints="",
        dependency_interfaces={},
        dependency_context={},
        dependency_usage={},
        vars={},
        glossary="",
        hint_code=None,
        spec_bundle_parts={},
    )


@pytest.fixture
def repo_root(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    root = tmp_path / "repo"
    comp = root / "specs" / "components" / "widget-maker"
    comp.mkdir(parents=True)
    (comp / "component.md").write_text(COMPONENT_MD, encoding="utf-8")
    adapter_dir = root / "gen" / "kind-python"
    adapter_dir.mkdir(parents=True)
    (adapter_dir / "kind_python.py").write_text(PYTHON_ADAPTER, encoding="utf-8")
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


def make_backend(build_reply, log_path):
    def backend(prompt, model, **params):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write("call\n")
        m = re.search(r"-----BEGIN FILE ([0-9a-f]{32}):", prompt)
        nonce = m.group(1)
        return {
            "text": build_reply(nonce),
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    return backend


def run(repo_root, tmp_path, build_reply):
    log_path = tmp_path / "mock_calls.log"
    backend = make_backend(build_reply, log_path)
    result = generator.generate(
        make_bundle(), MODEL, repo_root=repo_root, llm_backend=backend
    )
    return result, log_path


def assert_nothing_cached(repo_root):
    cm = load_cache_manager(repo_root)
    key = cm.CacheKey(
        spec_bundle_hash=make_bundle()["spec_bundle_hash"],
        gate_inputs_hash="sha256:"
        + hashlib.sha256(json.dumps(sorted([]), sort_keys=True).encode("utf-8")).hexdigest(),
        gate_version=generator.GATE_VERSION,
        model_pin=MODEL,
    )
    assert isinstance(cm.get(key, repo_root=repo_root), cm.Miss)
    assert field(cm.stats(repo_root=repo_root), "entry_count") == 0


def error_of(result):
    err = field(result, "model_call_error")
    assert err is not None
    return err


def test_complete_block_without_end_reply_is_truncated(repo_root, tmp_path):
    def reply(nonce):
        return block(nonce, "widget_maker.py", "X = 1\n")

    result, log_path = run(repo_root, tmp_path, reply)
    assert log_path.exists()
    err = error_of(result)
    assert field(err, "category") == "truncated_response"
    assert field(result, "files") == {}
    assert not (repo_root / "gen" / "widget-maker").exists()
    assert_nothing_cached(repo_root)


def test_unclosed_file_block_with_end_reply_names_path(repo_root, tmp_path):
    def reply(nonce):
        return (
            block(nonce, "widget_maker.py", "X = 1\n")
            + begin(nonce, "helpers.py")
            + "def helper():\n    return 1\n"
            + end_reply(nonce)
        )

    result, _ = run(repo_root, tmp_path, reply)
    err = error_of(result)
    assert field(err, "category") == "truncated_response"
    assert "helpers.py" in field(err, "message")
    assert field(result, "files") == {}
    assert not (repo_root / "gen" / "widget-maker").exists()


def test_unclosed_file_block_without_end_reply_names_path(repo_root, tmp_path):
    def reply(nonce):
        return (
            block(nonce, "widget_maker.py", "X = 1\n")
            + begin(nonce, "helpers.py")
            + "def helper():\n    return 1\n"
        )

    result, _ = run(repo_root, tmp_path, reply)
    err = error_of(result)
    assert field(err, "category") == "truncated_response"
    assert "helpers.py" in field(err, "message")
    assert field(result, "files") == {}


def test_reply_with_no_begin_file_is_empty_response(repo_root, tmp_path):
    def reply(nonce):
        return "I cannot help with that."

    result, _ = run(repo_root, tmp_path, reply)
    err = error_of(result)
    assert field(err, "category") == "empty_response"
    assert field(result, "files") == {}
    assert not (repo_root / "gen" / "widget-maker").exists()


def test_reply_without_module_is_missing_module(repo_root, tmp_path):
    def reply(nonce):
        return block(nonce, "notes.py", "NOTE = 1\n") + end_reply(nonce)

    result, _ = run(repo_root, tmp_path, reply)
    err = error_of(result)
    assert field(err, "category") == "missing_module"
    assert field(result, "files") == {}
    assert not (repo_root / "gen" / "widget-maker").exists()
    assert_nothing_cached(repo_root)


def test_package_reply_is_accepted_and_written(repo_root, tmp_path):
    init_content = "from .core import make_widget\n"
    core_content = "def make_widget():\n    return 'widget'\n"

    def reply(nonce):
        return (
            block(nonce, "widget_maker/__init__.py", init_content)
            + block(nonce, "widget_maker/core.py", core_content)
            + end_reply(nonce)
        )

    result, _ = run(repo_root, tmp_path, reply)
    assert field(result, "model_call_error") is None
    files = field(result, "files")
    assert files
    out = repo_root / "gen" / "widget-maker"
    init_path = out / "widget_maker" / "__init__.py"
    core_path = out / "widget_maker" / "core.py"
    assert init_path.is_file()
    assert core_path.is_file()
    assert init_path.read_text(encoding="utf-8") == init_content
    assert core_path.read_text(encoding="utf-8") == core_content