# hotdocs-criterion: sha256:1b6ad90e04bd0ce03c3e1a15c9f6ac7482dab7a3207a03c7ea45fcdc20fa8567
import importlib.util
import re
import sys
from pathlib import Path

import test_author


EXPECTED = "import os\n\n\ndef test_placeholder():\n    assert os.sep"


def load_module(path, module_name):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def body(content):
    first, _, rest = content.partition("\n")
    return rest if first.startswith("# hotdocs-criterion:") else content


def _gen_dir():
    return next(p for p in Path(test_author.__file__).resolve().parents if p.name == "gen")


def _load_dep(slug):
    module_name = slug.replace("-", "_")
    base = _gen_dir() / slug
    flat = base / (module_name + ".py")
    path = flat if flat.is_file() else base / module_name / "__init__.py"
    return load_module(path, module_name)


class _HybridBundle:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

    def __getitem__(self, key):
        return self.__dict__[key]

    def get(self, key, default=None):
        return self.__dict__.get(key, default)

    def keys(self):
        return self.__dict__.keys()

    def __iter__(self):
        return iter(self.__dict__)

    def __len__(self):
        return len(self.__dict__)


def _make_bundle():
    fields = dict(
        component_id="comp-foo",
        criterion_id="AC-FOO-001",
        covers="R-FOO-001",
        criterion_text="Given x = 2\nWhen foo(x) is called\nThen it returns 4",
        requirement_text="**R-FOO-001** — `foo(x)` MUST return `2 * x`.",
        interface="# Library\n\n```\nfoo(x: int) -> int\n```",
        glossary="# Glossary\n\n- **Foo** — a test term.",
        dependency_interfaces={},
    )
    try:
        sba = _load_dep("spec-bundle-assembler")
        cls = sba.CriterionBundle
        try:
            return cls(module_names=["foo"], **fields)
        except TypeError:
            return cls(**fields)
    except Exception:
        return _HybridBundle(module_names=["foo"], **fields)


def _mock_backend(reply_body, calls):
    def backend(prompt, model, **params):
        calls.append(prompt)
        m = re.search(r"-----BEGIN FILE ([0-9a-f]{32})-----", prompt)
        assert m, "prompt carries no BEGIN FILE nonce"
        n = m.group(1)
        text = "-----BEGIN FILE " + n + "-----\n" + reply_body + "\n-----END FILE " + n + "-----"
        return {"text": text, "model": model, "backend": "mock", "model_call_error": None}

    return backend


def test_ac_author_005_result_cached_under_correct_key(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    monkeypatch.chdir(tmp_path)
    repo_root = tmp_path

    cache_manager = _load_dep("cache-manager")

    # Given an empty cache
    assert field(cache_manager.stats(repo_root=repo_root), "entry_count") == 0

    bundle = _make_bundle()
    model = "claude-sonnet-5"

    # When author_test is called with a mock returning a fixed result
    calls = []
    result = test_author.author_test(
        bundle, model, 0, repo_root=repo_root, llm_backend=_mock_backend(EXPECTED, calls)
    )
    assert len(calls) == 1
    assert field(result, "model_call_error") is None
    assert field(result, "cache_hit") is False
    assert body(field(field(result, "file"), "content")) == EXPECTED

    # Then the cache holds that result afterward
    assert field(cache_manager.stats(repo_root=repo_root), "entry_count") == 1

    # ... under the key author_test itself looks up: a repeat call is served
    # from the cache, never reaching the model, with the same content.
    second_calls = []
    second = test_author.author_test(
        bundle,
        model,
        0,
        repo_root=repo_root,
        llm_backend=_mock_backend("import sys\n# a different reply", second_calls),
    )
    assert second_calls == []
    assert field(second, "cache_hit") is True
    assert field(second, "model_call_error") is None
    assert body(field(field(second, "file"), "content")) == EXPECTED
    assert field(cache_manager.stats(repo_root=repo_root), "entry_count") == 1