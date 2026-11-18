# hotdocs-criterion: sha256:e8ebdf83e3a63d8cbf70e1b135d82d2365aacb37d033314d3437d5f3f837d6fd
import importlib.util
import re
import sys
from pathlib import Path

import pytest

import test_author


MODEL = "claude-sonnet-5"
SLUG = "foo"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def load_module(path, module_name):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


class Bundle(dict):
    """A CriterionBundle readable both as a mapping and by attribute."""

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)


def make_bundle(dependency_interfaces):
    return Bundle(
        component_id="comp-foo",
        criterion_id="AC-FOO-001",
        covers="R-FOO-001",
        criterion_text=(
            "Given x = 2\n"
            "When foo(x) is called\n"
            "Then it returns 4\n"
        ),
        requirement_text="**R-FOO-001** \u2014 `foo(x)` MUST return `2 * x`.",
        interface="# Library\n\n```\nfoo(x: int) -> int\n```\n",
        glossary="# Glossary\n\n- **Foo** \u2014 a test term.\n",
        dependency_interfaces=dict(dependency_interfaces),
        module_names=["foo"],
    )


NONCE_RE = re.compile(r"-----BEGIN FILE ([0-9a-fA-F]+)-----")


def make_backend(content):
    def backend(prompt, model, **params):
        m = NONCE_RE.search(prompt)
        nonce = m.group(1) if m else "0" * 32
        text = (
            "-----BEGIN FILE " + nonce + "-----\n"
            + content
            + "\n-----END FILE " + nonce + "-----"
        )
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    return backend


def files_under(path):
    if not path.exists():
        return []
    return [p for p in path.rglob("*") if p.is_file()]


def cache_entry_count(repo_root):
    try:
        gen = next(
            p for p in Path(test_author.__file__).resolve().parents if p.name == "gen"
        )
    except StopIteration:
        return None
    base = gen / "cache-manager"
    if (base / "cache_manager.py").is_file():
        path = base / "cache_manager.py"
    elif (base / "cache_manager" / "__init__.py").is_file():
        path = base / "cache_manager" / "__init__.py"
    else:
        return None
    try:
        cm = load_module(path, "cache_manager")
    except Exception:
        return None
    stats = cm.stats(repo_root=repo_root)
    return field(stats, "entry_count")


def assert_nothing_written(repo_root):
    gt = repo_root / "verification" / SLUG / "generated-test"
    assert files_under(gt) == [], "a test file was written: " + repr(files_under(gt))
    cache_dir = repo_root / ".hotdocs" / "cache"
    assert files_under(cache_dir) == [], "cache was written: " + repr(files_under(cache_dir))
    count = cache_entry_count(repo_root)
    if count is not None:
        assert count == 0


def error_text(err):
    try:
        msg = field(err, "message")
    except (KeyError, AttributeError):
        msg = None
    return (str(msg) if msg is not None else "") + " " + str(err)


@pytest.fixture
def repo_root(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    root.mkdir()
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    monkeypatch.chdir(root)
    return root


DO_THING_IFACE = {
    "comp-bar": (
        "# Library\n\n"
        "```\n"
        "do_thing(a: int, b: str, c: dict[str, str]) -> bool\n"
        "```\n"
    )
}

SCAN_IFACES = {
    "comp-bar": (
        "# Library\n\n"
        "```\n"
        "scan(component_id: str, repo_root: Path) -> Report\n"
        "```\n"
    ),
    "comp-baz": (
        "# Library\n\n"
        "```\n"
        "scan(repo_root: Path) -> Report\n"
        "```\n"
    ),
}


def run(bundle, content, repo_root):
    return test_author.author_test(
        bundle, MODEL, 0, repo_root=repo_root, llm_backend=make_backend(content)
    )


def test_malformed_code_rejected(repo_root):
    content = "def (:\n    this is not python ??? }}}\n"
    result = run(make_bundle({}), content, repo_root)
    err = field(result, "model_call_error")
    assert err is not None
    assert field(err, "category") == "malformed_code"
    assert field(result, "file") is None
    assert_nothing_written(repo_root)


def test_two_arg_alias_fake_rejected(repo_root):
    content = (
        "import foo\n"
        "\n"
        "def _fake_do_thing(a, b):\n"
        "    return True\n"
        "\n"
        "do_thing = _fake_do_thing\n"
        "\n"
        "def test_foo():\n"
        "    assert foo.foo(2) == 4\n"
    )
    result = run(make_bundle(DO_THING_IFACE), content, repo_root)
    err = field(result, "model_call_error")
    assert err is not None
    assert field(err, "category") == "fake_signature_mismatch"
    assert "do_thing" in error_text(err)
    assert field(result, "file") is None
    assert_nothing_written(repo_root)


def test_three_arg_alias_fake_accepted(repo_root):
    content = (
        "import foo\n"
        "\n"
        "def _fake_do_thing(a, b, c):\n"
        "    return True\n"
        "\n"
        "do_thing = _fake_do_thing\n"
        "\n"
        "def test_foo():\n"
        "    assert foo.foo(2) == 4\n"
    )
    result = run(make_bundle(DO_THING_IFACE), content, repo_root)
    assert field(result, "model_call_error") is None
    f = field(result, "file")
    assert f is not None
    assert "_fake_do_thing(a, b, c)" in field(f, "content")


@pytest.mark.parametrize("params", ["component_id, repo_root", "repo_root"])
def test_scan_matching_any_dependency_arity_accepted(repo_root, params):
    content = (
        "import foo\n"
        "\n"
        "def scan(" + params + "):\n"
        "    return {}\n"
        "\n"
        "def test_foo():\n"
        "    assert foo.foo(2) == 4\n"
    )
    result = run(make_bundle(SCAN_IFACES), content, repo_root)
    assert field(result, "model_call_error") is None
    assert field(result, "file") is not None


def test_scan_three_params_rejected(repo_root):
    content = (
        "import foo\n"
        "\n"
        "def scan(component_id, repo_root, extra):\n"
        "    return {}\n"
        "\n"
        "def test_foo():\n"
        "    assert foo.foo(2) == 4\n"
    )
    result = run(make_bundle(SCAN_IFACES), content, repo_root)
    err = field(result, "model_call_error")
    assert err is not None
    assert field(err, "category") == "fake_signature_mismatch"
    assert "scan" in error_text(err)
    assert field(result, "file") is None
    assert_nothing_written(repo_root)