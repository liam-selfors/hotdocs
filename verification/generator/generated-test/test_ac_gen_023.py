# hotdocs-criterion: sha256:979a7782f7865aa92a93c9853d4d70876e27cde0ad7626ac3c1d0b779a76c3c2
import generator

import dataclasses
import importlib.util
import re
import sys
from pathlib import Path

import pytest


MODEL = "claude-sonnet-5"
COMPONENT_ID = "comp-widget-maker"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def load_module(path, module_name):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def load_tool_dependency(slug):
    gen = next(p for p in Path(generator.__file__).resolve().parents if p.name == "gen")
    module_name = slug.replace("-", "_")
    base = gen / slug
    flat = base / (module_name + ".py")
    path = flat if flat.is_file() else base / module_name / "__init__.py"
    return load_module(path, module_name)


@dataclasses.dataclass
class FakeSpecBundle:
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
    hint_code: object = None

    def __getitem__(self, key):
        if key not in {f.name for f in dataclasses.fields(self)}:
            raise KeyError(key)
        return getattr(self, key)

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default

    def keys(self):
        return [f.name for f in dataclasses.fields(self)]


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


@pytest.fixture
def repo_root(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    root = tmp_path / "repo"
    comp_dir = root / "specs" / "components" / "widget-maker"
    comp_dir.mkdir(parents=True)
    (comp_dir / "component.md").write_text(COMPONENT_MD, encoding="utf-8")
    adapter_dir = root / "gen" / "kind-python"
    adapter_dir.mkdir(parents=True)
    (adapter_dir / "kind_python.py").write_text(FAKE_PYTHON_ADAPTER, encoding="utf-8")
    monkeypatch.chdir(root)
    return root


def make_bundle():
    return FakeSpecBundle(
        component_id=COMPONENT_ID,
        spec_bundle_hash="sha256:" + "a" * 64,
        spec="# Widget Maker\n\nMakes widgets.",
        interface="make_widget() -> str",
        constraints="None.",
    )


def begin(nonce, path):
    return "-----BEGIN FILE " + nonce + ": " + path + "-----\n"


def end_file(nonce):
    return "-----END FILE " + nonce + "-----\n"


def end_reply(nonce):
    return "-----END REPLY " + nonce + "-----\n"


def block(nonce, path, content):
    return begin(nonce, path) + content + end_file(nonce)


def make_backend(build_reply, calls):
    def backend(prompt, model, **params):
        calls.append(prompt)
        m = re.search(r"-----BEGIN FILE ([0-9a-f]{32}):", prompt)
        nonce = m.group(1) if m else "0" * 32
        return {
            "text": build_reply(nonce),
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }
    return backend


def run(repo_root, build_reply):
    calls = []
    result = generator.generate(
        make_bundle(), MODEL, repo_root=repo_root,
        llm_backend=make_backend(build_reply, calls),
    )
    assert calls, "mock model was never called"
    return result


def error_of(result):
    err = field(result, "model_call_error")
    assert err is not None, "expected a model_call_error"
    return err


def cache_entry_count(repo_root):
    cache_manager = load_tool_dependency("cache-manager")
    return field(cache_manager.stats(repo_root=repo_root), "entry_count")


WIDGET_CONTENT = "def make_widget():\n    return 'widget'\n"


def test_complete_block_without_end_reply_is_truncated(repo_root):
    def reply(nonce):
        return block(nonce, "widget_maker.py", WIDGET_CONTENT)

    result = run(repo_root, reply)
    err = error_of(result)
    assert field(err, "category") == "truncated_response"
    assert field(result, "files") == {}
    assert not (repo_root / "gen" / "widget-maker").exists()
    assert cache_entry_count(repo_root) == 0


def test_unterminated_file_block_with_end_reply_names_file(repo_root):
    def reply(nonce):
        return (
            block(nonce, "widget_maker.py", WIDGET_CONTENT)
            + begin(nonce, "helpers.py")
            + "def helper():\n    return 1\n"
            + end_reply(nonce)
        )

    result = run(repo_root, reply)
    err = error_of(result)
    assert field(err, "category") == "truncated_response"
    assert "helpers.py" in field(err, "message")


def test_unterminated_file_block_without_end_reply_names_file(repo_root):
    def reply(nonce):
        return (
            block(nonce, "widget_maker.py", WIDGET_CONTENT)
            + begin(nonce, "helpers.py")
            + "def helper():\n    return 1\n"
        )

    result = run(repo_root, reply)
    err = error_of(result)
    assert field(err, "category") == "truncated_response"
    assert "helpers.py" in field(err, "message")


def test_reply_with_no_blocks_is_empty_response(repo_root):
    def reply(nonce):
        return "I cannot help with that."

    result = run(repo_root, reply)
    err = error_of(result)
    assert field(err, "category") == "empty_response"


def test_reply_without_module_is_missing_module(repo_root):
    def reply(nonce):
        return block(nonce, "notes.py", "NOTES = 1\n") + end_reply(nonce)

    result = run(repo_root, reply)
    err = error_of(result)
    assert field(err, "category") == "missing_module"
    assert field(result, "files") == {}
    assert not (repo_root / "gen" / "widget-maker").exists()
    assert cache_entry_count(repo_root) == 0


def test_package_reply_is_accepted_and_written(repo_root):
    init_content = "from .core import make_widget\n"
    core_content = WIDGET_CONTENT

    def reply(nonce):
        return (
            block(nonce, "widget_maker/__init__.py", init_content)
            + block(nonce, "widget_maker/core.py", core_content)
            + end_reply(nonce)
        )

    result = run(repo_root, reply)
    assert field(result, "model_call_error") is None
    out = repo_root / "gen" / "widget-maker" / "widget_maker"
    init_file = out / "__init__.py"
    core_file = out / "core.py"
    assert init_file.is_file()
    assert core_file.is_file()
    assert init_file.read_text(encoding="utf-8") == init_content
    assert core_file.read_text(encoding="utf-8") == core_content