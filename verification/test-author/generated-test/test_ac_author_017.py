# hotdocs-criterion: sha256:2b035f8dbdc356ce0cb8e88a854be98c8cd1bdf16afac2f3fa71b4ae308c7699
import re

import pytest

import test_author


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def body(content):
    first, _, rest = content.partition("\n")
    return rest if first.startswith("# hotdocs-criterion:") else content


EXPECTED = "import foo\n\n\ndef test_foo_doubles():\n    assert foo.foo(2) == 4"


def make_backend(calls):
    def backend(prompt, model, **params):
        calls.append(prompt)
        nonces = re.findall(r"-----BEGIN FILE ([0-9a-f]{32})-----", prompt)
        assert nonces, "prompt carries no BEGIN FILE nonce"
        n = nonces[0]
        text = "-----BEGIN FILE " + n + "-----\n" + EXPECTED + "\n-----END FILE " + n + "-----"
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    return backend


class PlainBundle:
    """CriterionBundle-shaped plain object with no dependency_interfaces attribute."""

    def __init__(self):
        self.component_id = "comp-foo"
        self.criterion_id = "AC-FOO-001"
        self.covers = "R-FOO-001"
        self.criterion_text = "Given x = 2\nWhen foo(x) is called\nThen it returns 4"
        self.requirement_text = "**R-FOO-001** — `foo(x)` MUST return `2 * x`."
        self.interface = "# Library\n\n```\nfoo(x: int) -> int\n```"
        self.glossary = "# Glossary\n\n- **Foo** — a test term."
        self.module_names = ["foo"]


def dict_bundle():
    return {
        "component_id": "comp-foo",
        "criterion_id": "AC-FOO-001",
        "covers": "R-FOO-001",
        "criterion_text": "Given x = 2\nWhen foo(x) is called\nThen it returns 4",
        "requirement_text": "**R-FOO-001** — `foo(x)` MUST return `2 * x`.",
        "interface": "# Library\n\n```\nfoo(x: int) -> int\n```",
        "glossary": "# Glossary\n\n- **Foo** — a test term.",
        "module_names": ["foo"],
    }


def assert_completed(result, calls):
    assert len(calls) >= 1
    assert field(result, "model_call_error") is None
    assert field(result, "component_id") == "comp-foo"
    assert field(result, "criterion_id") == "AC-FOO-001"
    file_value = field(result, "file")
    assert file_value is not None
    assert body(field(file_value, "content")) == EXPECTED


def test_object_bundle_without_dependency_interfaces_attribute(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    bundle = PlainBundle()
    assert not hasattr(bundle, "dependency_interfaces")
    calls = []
    try:
        result = test_author.author_test(
            bundle, "mock-model", 0,
            repo_root=repo_root, llm_backend=make_backend(calls),
        )
    except AttributeError as exc:
        pytest.fail("author_test raised AttributeError: " + repr(exc))
    assert_completed(result, calls)


def test_dict_bundle_missing_dependency_interfaces_key(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    bundle = dict_bundle()
    assert "dependency_interfaces" not in bundle
    calls = []
    try:
        result = test_author.author_test(
            bundle, "mock-model", 0,
            repo_root=repo_root, llm_backend=make_backend(calls),
        )
    except KeyError as exc:
        pytest.fail("author_test raised KeyError: " + repr(exc))
    assert_completed(result, calls)