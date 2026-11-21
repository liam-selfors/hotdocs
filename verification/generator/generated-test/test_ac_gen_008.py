# hotdocs-criterion: sha256:15d14c0b5ede2aa2cac3c4f0c6c483bdb2f7d97a92e425fea5b8e77c6c59a634
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

import generator


PY_ADAPTER_SOURCE = (
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

MODEL = "mock-model"
BUNDLE_HASH = "sha256:" + "0" * 64


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


def make_repo(tmp_path):
    repo_root = tmp_path / "repo"
    adapter = repo_root / "gen" / "kind-python" / "kind_python.py"
    adapter.parent.mkdir(parents=True)
    adapter.write_text(PY_ADAPTER_SOURCE, encoding="utf-8")
    comp = repo_root / "specs" / "components" / "widget-maker" / "component.md"
    comp.parent.mkdir(parents=True)
    comp.write_text(COMPONENT_MD, encoding="utf-8")
    return repo_root


def make_bundle():
    return {
        "component_id": "comp-widget-maker",
        "spec_bundle_hash": BUNDLE_HASH,
        "spec": "# Widget Maker\n\nMakes widgets.",
        "interface": "def make_widget() -> str",
        "constraints": "",
        "dependency_interfaces": {},
        "dependency_context": {},
        "dependency_usage": {},
        "vars": {},
        "glossary": "",
        "hint_code": None,
    }


def text_backend(text):
    def backend(prompt, model, **params):
        return {"text": text, "model": model, "backend": "mock", "model_call_error": None}
    return backend


def network_error_backend(prompt, model, **params):
    return {
        "text": None,
        "model": model,
        "backend": "mock",
        "model_call_error": {"category": "network", "message": "connection failed"},
    }


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    repo_root = make_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    return repo_root


def run(repo_root, backend):
    return generator.generate(make_bundle(), MODEL, None, repo_root=repo_root, llm_backend=backend)


def assert_nothing_written_or_cached(repo_root):
    gen_dir = repo_root / "gen" / "widget-maker"
    assert not gen_dir.exists() or not any(gen_dir.iterdir())
    cache_manager = load_cache_manager()
    key = cache_manager.CacheKey(
        spec_bundle_hash=BUNDLE_HASH,
        gate_inputs_hash="sha256:" + hashlib.sha256(
            json.dumps(sorted([]), sort_keys=True).encode("utf-8")
        ).hexdigest(),
        gate_version=generator.GATE_VERSION,
        model_pin=MODEL,
    )
    assert isinstance(cache_manager.get(key, repo_root=repo_root), cache_manager.Miss)
    assert field(cache_manager.stats(repo_root=repo_root), "entry_count") == 0


def test_network_error_is_model_call_error(env):
    result = run(env, network_error_backend)
    assert field(result, "model_call_error") is not None
    assert field(result, "files") == {}
    assert field(result, "cache_hit") is False


def test_reply_with_no_file_blocks_is_empty_response(env):
    text = "I cannot: the bundle omits X."
    result = run(env, text_backend(text))
    err = field(result, "model_call_error")
    assert err is not None
    assert field(err, "category") == "empty_response"
    assert field(err, "message") == (
        "the model reply contained no files; it began:\nI cannot: the bundle omits X."
    )
    assert field(result, "files") == {}
    assert field(result, "cache_hit") is False
    assert_nothing_written_or_cached(env)


def test_long_reply_message_is_truncated_with_count(env):
    text = "a" * 4010
    result = run(env, text_backend(text))
    err = field(result, "model_call_error")
    assert err is not None
    assert field(err, "category") == "empty_response"
    assert field(err, "message").endswith("\n[10 more characters]")
    assert field(result, "files") == {}
    assert field(result, "cache_hit") is False


def test_whitespace_only_reply_is_empty(env):
    result = run(env, text_backend("  \n"))
    err = field(result, "model_call_error")
    assert err is not None
    assert field(err, "category") == "empty_response"
    assert field(err, "message") == "the model reply was empty"
    if isinstance(err, dict):
        assert err == {"category": "empty_response", "message": "the model reply was empty"}
    assert field(result, "files") == {}
    assert field(result, "cache_hit") is False