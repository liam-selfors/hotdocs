# hotdocs-criterion: sha256:e0e9eef398cbcc5122a9f6e5a0cca41463ce7f3e6fb3f30c8862a343349979d7
import importlib.util
import re
import sys
from pathlib import Path

import pytest

import generator


PYTHON_ADAPTER = (
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
    "    return {\"ok\": True, \"reason\": \"\", \"versions\": {\"python\": \"3.12\"}, \"lockfile_sha256\": None, \"interpreter\": \"/fake/python\"}\n"
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

PREFIX = "the model reply contained no files; it began:\n"


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
    path = base / "cache_manager.py" if (base / "cache_manager.py").is_file() else base / "cache_manager" / "__init__.py"
    return load_module(path, "cache_manager")


@pytest.fixture
def repo_root(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    root = tmp_path / "repo"
    adapter = root / "gen" / "kind-python" / "kind_python.py"
    adapter.parent.mkdir(parents=True)
    adapter.write_text(PYTHON_ADAPTER, encoding="utf-8")
    comp = root / "specs" / "components" / "widget-maker" / "component.md"
    comp.parent.mkdir(parents=True)
    comp.write_text(COMPONENT_MD, encoding="utf-8")
    return root


def make_bundle(tag):
    return {
        "component_id": "comp-widget-maker",
        "spec_bundle_hash": "sha256:" + (tag * 64)[:64],
        "spec": "# Widget Maker\n\nMakes widgets.",
        "interface": "make() -> str",
        "constraints": "",
        "dependency_interfaces": {},
        "dependency_context": {},
        "dependency_usage": {},
        "vars": {},
        "glossary": "",
        "hint_code": None,
        "spec_bundle_parts": {},
    }


def text_backend(text, log_path):
    def backend(prompt, model, **params):
        assert re.search(r"-----BEGIN FILE ([0-9a-f]{32}):", prompt)
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write("called\n")
        return {"text": text, "model": model, "backend": "mock", "model_call_error": None}

    return backend


def assert_nothing_written_or_cached(repo_root):
    gen_dir = repo_root / "gen" / "widget-maker"
    assert not gen_dir.exists() or not any(gen_dir.iterdir())
    cache_manager = load_cache_manager()
    assert field(cache_manager.stats(repo_root=repo_root), "entry_count") == 0


def test_network_error(repo_root):
    def backend(prompt, model, **params):
        raise ConnectionError("network unreachable")

    result = generator.generate(make_bundle("a"), "mock-model", repo_root=repo_root, llm_backend=backend)
    assert field(result, "model_call_error") is not None
    assert field(result, "files") == {}
    assert field(result, "cache_hit") is False


def test_reply_without_files(repo_root, tmp_path):
    log = tmp_path / "calls.log"
    text = "I cannot: the bundle omits X."
    result = generator.generate(
        make_bundle("b"), "mock-model", repo_root=repo_root, llm_backend=text_backend(text, log)
    )
    assert log.read_text(encoding="utf-8").count("called") == 1
    err = field(result, "model_call_error")
    assert err is not None
    assert field(err, "category") == "empty_response"
    assert field(err, "message") == PREFIX + "I cannot: the bundle omits X."
    assert field(result, "files") == {}
    assert field(result, "cache_hit") is False
    assert_nothing_written_or_cached(repo_root)


def test_long_reply_truncated(repo_root, tmp_path):
    log = tmp_path / "calls.log"
    text = "a" * 4010
    result = generator.generate(
        make_bundle("c"), "mock-model", repo_root=repo_root, llm_backend=text_backend(text, log)
    )
    err = field(result, "model_call_error")
    assert err is not None
    assert field(err, "category") == "empty_response"
    message = field(err, "message")
    assert message.endswith("\n[10 more characters]")
    assert message == PREFIX + "a" * 4000 + "\n[10 more characters]"
    assert field(result, "files") == {}
    assert field(result, "cache_hit") is False


def test_whitespace_reply(repo_root, tmp_path):
    log = tmp_path / "calls.log"
    result = generator.generate(
        make_bundle("d"), "mock-model", repo_root=repo_root, llm_backend=text_backend("  \n", log)
    )
    err = field(result, "model_call_error")
    assert dict(err) == {"category": "empty_response", "message": "the model reply was empty"}
    assert field(result, "files") == {}
    assert field(result, "cache_hit") is False