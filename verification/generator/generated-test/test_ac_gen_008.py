# hotdocs-criterion: sha256:b0c2fd8d2d16ef7a247a59f4b8d3f1943421ea20368c677b754e6181906a7dda
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

import generator


COMPONENT_ID = "comp-foo"
SLUG = "foo"
MODEL = "anthropic:claude-sonnet-5"
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
        spec_bundle_hash=BUNDLE_HASH,
        spec="# Foo\n\n## Purpose\n\nFoo doubles a number.\n\n# R-FOO-001\n\n**R-FOO-001** \u2014 `foo(x)` MUST return `2 * x`.",
        interface="# Library\n\n```\nfoo(x: int) -> int\n```",
        constraints="# Constraints\n\nNone.",
        dependency_interfaces={},
        dependency_context={},
        dependency_usage={},
        vars={},
        glossary="# Glossary\n\n- **Foo** \u2014 a test term.",
        hint_code=None,
    )


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_repo(repo_root):
    write(repo_root / "specs" / "glossary.md", "# Glossary\n\n- **Foo** \u2014 a test term.\n")
    comp = repo_root / "specs" / "components" / SLUG
    write(
        comp / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "sealed: false\n"
        "depends_on: []\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Foo doubles a number.\n",
    )
    write(
        comp / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n\n**R-FOO-001** \u2014 `foo(x)` MUST return `2 * x`.\n",
    )
    write(
        comp / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n\nCovers: R-FOO-001\nKind: generated-test\n\n```gherkin\nGiven x = 2\nWhen foo(x) is called\nThen it returns 4\n```\n",
    )
    write(comp / "interface" / "library.md", "# Library\n\n```\nfoo(x: int) -> int\n```\n")
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")


@pytest.fixture
def repo_root(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    root = tmp_path / "repo"
    root.mkdir()
    build_repo(root)
    monkeypatch.chdir(root)
    return root


def make_text_backend(text, log_path):
    def backend(prompt, model, **params):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write("call\n")
        return {"text": text, "model": model, "backend": "mock", "model_call_error": None}

    return backend


def calls(log_path):
    if not log_path.exists():
        return 0
    return len([l for l in log_path.read_text(encoding="utf-8").splitlines() if l.strip()])


def gen_files(repo_root):
    d = repo_root / "gen" / SLUG
    if not d.exists():
        return []
    return [p for p in d.rglob("*") if p.is_file()]


def assert_nothing_cached(repo_root):
    cm = load_cache_manager()
    stats = cm.stats(repo_root=repo_root)
    assert field(stats, "entry_count") == 0
    key = cm.CacheKey(
        spec_bundle_hash=BUNDLE_HASH,
        gate_inputs_hash="sha256:" + hashlib.sha256(
            json.dumps(sorted([]), sort_keys=True).encode("utf-8")
        ).hexdigest(),
        gate_version=generator.GATE_VERSION,
        model_pin=MODEL,
    )
    assert isinstance(cm.get(key, repo_root=repo_root), cm.Miss)


def assert_failed_result(result):
    assert field(result, "model_call_error") is not None
    assert not field(result, "files")
    assert field(result, "cache_hit") is False
    assert field(result, "refused") is None


# --- Scenario 1: network error ---------------------------------------------

def test_network_error_raised_by_mock_is_model_call_error(repo_root, tmp_path):
    log_path = tmp_path / "calls.log"

    def backend(prompt, model, **params):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write("call\n")
        raise ConnectionError("network unreachable")

    result = generator.generate(make_bundle(), MODEL, repo_root=repo_root, llm_backend=backend)

    assert calls(log_path) >= 1
    assert_failed_result(result)
    assert gen_files(repo_root) == []
    assert_nothing_cached(repo_root)


def test_network_error_reported_by_mock_is_model_call_error(repo_root, tmp_path):
    log_path = tmp_path / "calls.log"

    def backend(prompt, model, **params):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write("call\n")
        return {
            "text": None,
            "model": model,
            "backend": "mock",
            "model_call_error": {"category": "network", "message": "network unreachable"},
        }

    result = generator.generate(make_bundle(), MODEL, repo_root=repo_root, llm_backend=backend)

    assert calls(log_path) >= 1
    assert_failed_result(result)
    assert gen_files(repo_root) == []
    assert_nothing_cached(repo_root)


# --- Scenario 2: reply with no file blocks ---------------------------------

def test_reply_without_files_is_empty_response(repo_root, tmp_path):
    log_path = tmp_path / "calls.log"
    text = "I cannot: the bundle omits X."
    backend = make_text_backend(text, log_path)

    result = generator.generate(make_bundle(), MODEL, repo_root=repo_root, llm_backend=backend)

    assert calls(log_path) >= 1
    assert_failed_result(result)
    err = field(result, "model_call_error")
    assert field(err, "category") == "empty_response"
    assert field(err, "message") == (
        "the model reply contained no files; it began:\nI cannot: the bundle omits X."
    )
    assert gen_files(repo_root) == []
    assert_nothing_cached(repo_root)


# --- Scenario 3: long reply truncated ---------------------------------------

def test_long_reply_without_files_is_truncated(repo_root, tmp_path):
    log_path = tmp_path / "calls.log"
    text = "a" * 4010
    backend = make_text_backend(text, log_path)

    result = generator.generate(make_bundle(), MODEL, repo_root=repo_root, llm_backend=backend)

    assert calls(log_path) >= 1
    assert_failed_result(result)
    err = field(result, "model_call_error")
    assert field(err, "category") == "empty_response"
    message = field(err, "message")
    assert message.endswith("\n[10 more characters]")
    assert message == (
        "the model reply contained no files; it began:\n"
        + "a" * 4000
        + "\n[10 more characters]"
    )
    assert gen_files(repo_root) == []
    assert_nothing_cached(repo_root)


# --- Scenario 4: whitespace-only reply --------------------------------------

def test_whitespace_reply_is_empty(repo_root, tmp_path):
    log_path = tmp_path / "calls.log"
    backend = make_text_backend("  \n", log_path)

    result = generator.generate(make_bundle(), MODEL, repo_root=repo_root, llm_backend=backend)

    assert calls(log_path) >= 1
    assert_failed_result(result)
    err = field(result, "model_call_error")
    assert field(err, "category") == "empty_response"
    assert field(err, "message") == "the model reply was empty"
    if isinstance(err, dict):
        assert err == {"category": "empty_response", "message": "the model reply was empty"}
    assert gen_files(repo_root) == []
    assert_nothing_cached(repo_root)