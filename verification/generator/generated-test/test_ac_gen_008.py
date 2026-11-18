# hotdocs-criterion: sha256:b0c2fd8d2d16ef7a247a59f4b8d3f1943421ea20368c677b754e6181906a7dda
import importlib.util
import sys
from pathlib import Path

import pytest

import generator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def load_module(path, module_name):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


class Bundle:
    """A SpecBundle-shaped object readable both by attribute and as a mapping."""

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

    def __init__(self):
        self.component_id = "comp-foo"
        self.spec_bundle_hash = "sha256:" + "ab" * 32
        self.spec = "# Foo\n\n## Purpose\n\nFoo doubles a number.\n\n# R-FOO-001\n\n**R-FOO-001** \u2014 `foo(x)` MUST return `2 * x`."
        self.interface = "# Library\n\n```\nfoo(x: int) -> int\n```"
        self.constraints = "# Constraints\n\nNone."
        self.dependency_interfaces = {}
        self.dependency_context = {}
        self.dependency_usage = {}
        self.vars = {}
        self.glossary = "# Glossary\n\n- **Foo** \u2014 a test term."
        self.hint_code = None

    def __getitem__(self, key):
        if key not in self._FIELDS:
            raise KeyError(key)
        return getattr(self, key)

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default

    def keys(self):
        return list(self._FIELDS)

    def __iter__(self):
        return iter(self._FIELDS)

    def __len__(self):
        return len(self._FIELDS)

    def __contains__(self, key):
        return key in self._FIELDS


def make_text_backend(text, log_path):
    def backend(prompt, model, **params):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write("call\n")
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    return backend


def make_network_error_backend(log_path):
    def backend(prompt, model, **params):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write("call\n")
        return {
            "text": None,
            "model": model,
            "backend": "mock",
            "model_call_error": {"category": "network", "message": "connection failed"},
        }

    return backend


def _load_cache_manager():
    gen = next(p for p in Path(generator.__file__).resolve().parents if p.name == "gen")
    base = gen / "cache-manager"
    path = base / "cache_manager.py" if (base / "cache_manager.py").is_file() else base / "cache_manager" / "__init__.py"
    return load_module(path, "cache_manager")


def _call_count(log_path):
    if not log_path.exists():
        return 0
    return len([ln for ln in log_path.read_text(encoding="utf-8").splitlines() if ln.strip()])


def _assert_nothing_written_or_cached(repo_root):
    gen_dir = repo_root / "gen" / "foo"
    assert not gen_dir.exists() or not any(gen_dir.iterdir())
    cache_manager = _load_cache_manager()
    stats = cache_manager.stats(repo_root=repo_root)
    assert field(stats, "entry_count") == 0


@pytest.fixture
def repo_root(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    root = tmp_path / "repo"
    root.mkdir()
    return root


def _run(repo_root, backend):
    return generator.generate(
        Bundle(), "mock-model", None, repo_root=repo_root, llm_backend=backend
    )


def test_network_error_is_model_call_error(repo_root, tmp_path):
    log_path = tmp_path / "calls.log"
    result = _run(repo_root, make_network_error_backend(log_path))

    assert _call_count(log_path) >= 1
    err = field(result, "model_call_error")
    assert err is not None
    assert field(result, "files") == {}
    assert field(result, "cache_hit") is False
    assert field(result, "refused") is None


def test_reply_without_file_blocks_is_empty_response(repo_root, tmp_path):
    log_path = tmp_path / "calls.log"
    text = "I cannot: the bundle omits X."
    result = _run(repo_root, make_text_backend(text, log_path))

    assert _call_count(log_path) >= 1
    err = field(result, "model_call_error")
    assert err is not None
    assert field(err, "category") == "empty_response"
    assert field(err, "message") == (
        "the model reply contained no files; it began:\nI cannot: the bundle omits X."
    )
    assert field(result, "files") == {}
    assert field(result, "cache_hit") is False
    assert field(result, "refused") is None
    _assert_nothing_written_or_cached(repo_root)


def test_long_reply_without_file_blocks_is_truncated(repo_root, tmp_path):
    log_path = tmp_path / "calls.log"
    text = "a" * 4010
    result = _run(repo_root, make_text_backend(text, log_path))

    assert _call_count(log_path) >= 1
    err = field(result, "model_call_error")
    assert err is not None
    assert field(err, "category") == "empty_response"
    message = field(err, "message")
    assert message.startswith("the model reply contained no files; it began:\n")
    assert message.endswith("\n[10 more characters]")
    assert field(result, "files") == {}
    assert field(result, "cache_hit") is False
    _assert_nothing_written_or_cached(repo_root)


def test_whitespace_only_reply_is_empty(repo_root, tmp_path):
    log_path = tmp_path / "calls.log"
    result = _run(repo_root, make_text_backend("  \n", log_path))

    assert _call_count(log_path) >= 1
    err = field(result, "model_call_error")
    assert err is not None
    assert field(err, "category") == "empty_response"
    assert field(err, "message") == "the model reply was empty"
    if isinstance(err, dict):
        assert err == {"category": "empty_response", "message": "the model reply was empty"}
    assert field(result, "files") == {}
    assert field(result, "cache_hit") is False
    _assert_nothing_written_or_cached(repo_root)