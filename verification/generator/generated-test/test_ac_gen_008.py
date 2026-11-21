# hotdocs-criterion: sha256:c9a9662b8d65b15ac55f91d3eeb9cc03e41ef0ef1b99c769d8baae5463abb2fb
import importlib.util
import sys
import uuid
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
    "    return {\"ok\": True, \"reason\": \"\", \"versions\": {\"python\": \"3.12\"}, "
    "\"lockfile_sha256\": None, \"interpreter\": \"/fake/python\"}\n"
)


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


class Bundle:
    """A SpecBundle-shaped object readable by attribute and as a mapping."""

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

    def __init__(self, **kwargs):
        for name in self._FIELDS:
            setattr(self, name, kwargs[name])

    def __getitem__(self, key):
        if key not in self._FIELDS:
            raise KeyError(key)
        return getattr(self, key)

    def get(self, key, default=None):
        return getattr(self, key) if key in self._FIELDS else default

    def keys(self):
        return list(self._FIELDS)

    def __iter__(self):
        return iter(self._FIELDS)

    def __len__(self):
        return len(self._FIELDS)

    def __contains__(self, key):
        return key in self._FIELDS


def make_bundle():
    return Bundle(
        component_id="comp-widget-maker",
        spec_bundle_hash="sha256:" + uuid.uuid4().hex + uuid.uuid4().hex,
        spec="# Widget Maker\n\nMakes widgets.",
        interface="# Library\n\nmake() -> str",
        constraints="None.",
        dependency_interfaces={},
        dependency_context={},
        dependency_usage={},
        vars={},
        glossary="",
        hint_code=None,
    )


MODEL = "anthropic:claude-sonnet-5"


@pytest.fixture
def repo_root(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    root = tmp_path / "repo"
    root.mkdir()
    adapter = root / "gen" / "kind-python" / "kind_python.py"
    adapter.parent.mkdir(parents=True)
    adapter.write_text(PYTHON_ADAPTER, encoding="utf-8")
    monkeypatch.chdir(root)
    return root


def text_backend(text, calls):
    def backend(prompt, model, **params):
        calls.append(prompt)
        return {"text": text, "model": model, "backend": "mock", "model_call_error": None}

    return backend


def nothing_written_or_cached(repo_root):
    out_dir = repo_root / "gen" / "widget-maker"
    if out_dir.exists():
        assert [p for p in out_dir.rglob("*") if p.is_file()] == []
    cache_manager = load_cache_manager()
    stats = cache_manager.stats(repo_root=repo_root)
    assert field(stats, "entry_count") == 0


def test_network_error_is_model_call_error(repo_root):
    calls = []

    def backend(prompt, model, **params):
        calls.append(prompt)
        return {
            "text": None,
            "model": model,
            "backend": "mock",
            "model_call_error": {"category": "network", "message": "connection refused"},
        }

    result = generator.generate(make_bundle(), MODEL, repo_root=repo_root, llm_backend=backend)

    assert len(calls) == 1
    assert field(result, "model_call_error") is not None
    assert field(result, "files") == {}
    assert field(result, "cache_hit") is False


def test_reply_with_no_file_blocks_is_empty_response(repo_root):
    calls = []
    backend = text_backend("I cannot: the bundle omits X.", calls)

    result = generator.generate(make_bundle(), MODEL, repo_root=repo_root, llm_backend=backend)

    assert len(calls) == 1
    error = field(result, "model_call_error")
    assert error is not None
    assert field(error, "category") == "empty_response"
    assert field(error, "message") == (
        "the model reply contained no files; it began:\nI cannot: the bundle omits X."
    )
    assert field(result, "files") == {}
    assert field(result, "cache_hit") is False
    nothing_written_or_cached(repo_root)


def test_long_reply_with_no_file_blocks_is_truncated(repo_root):
    calls = []
    backend = text_backend("a" * 4010, calls)

    result = generator.generate(make_bundle(), MODEL, repo_root=repo_root, llm_backend=backend)

    assert len(calls) == 1
    error = field(result, "model_call_error")
    assert error is not None
    assert field(error, "category") == "empty_response"
    message = field(error, "message")
    assert message.endswith("\n[10 more characters]")
    assert message == (
        "the model reply contained no files; it began:\n" + "a" * 4000 + "\n[10 more characters]"
    )
    assert field(result, "files") == {}
    assert field(result, "cache_hit") is False


def test_whitespace_only_reply_is_empty(repo_root):
    calls = []
    backend = text_backend("  \n", calls)

    result = generator.generate(make_bundle(), MODEL, repo_root=repo_root, llm_backend=backend)

    assert len(calls) == 1
    error = field(result, "model_call_error")
    assert dict(error) == {"category": "empty_response", "message": "the model reply was empty"}
    assert field(result, "files") == {}
    assert field(result, "cache_hit") is False
    nothing_written_or_cached(repo_root)