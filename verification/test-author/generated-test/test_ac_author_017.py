import re

import pytest

import test_author


EXPECTED_BODY = "import os\n\n\ndef test_placeholder():\n    assert os.sep\n"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def body(content):
    first, _, rest = content.partition("\n")
    return rest if first.startswith("# hotdocs-criterion:") else content


def make_backend(calls):
    def backend(prompt, model, **params):
        calls.append(prompt)
        m = re.search(r"-----BEGIN FILE ([0-9a-fA-F]{32})-----", prompt)
        assert m is not None, "prompt carries no BEGIN FILE nonce marker"
        n = m.group(1)
        text = (
            "-----BEGIN FILE " + n + "-----\n"
            + EXPECTED_BODY
            + "\n-----END FILE " + n + "-----"
        )
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    return backend


class PlainBundle:
    """A CriterionBundle-shaped plain object with no dependency_interfaces."""

    def __init__(self, criterion_id):
        self.component_id = "comp-foo"
        self.criterion_id = criterion_id
        self.covers = "R-FOO-001"
        self.criterion_text = (
            "Given x = 2\nWhen foo(x) is called\nThen it returns 4"
        )
        self.requirement_text = "**R-FOO-001** — `foo(x)` MUST return `2 * x`."
        self.interface = "# Library\n\n```\nfoo(x: int) -> int\n```"
        self.glossary = "# Glossary\n\n- **Foo** — a test term."
        self.module_names = ["foo"]


def dict_bundle(criterion_id):
    return {
        "component_id": "comp-foo",
        "criterion_id": criterion_id,
        "covers": "R-FOO-001",
        "criterion_text": "Given x = 2\nWhen foo(x) is called\nThen it returns 4",
        "requirement_text": "**R-FOO-001** — `foo(x)` MUST return `2 * x`.",
        "interface": "# Library\n\n```\nfoo(x: int) -> int\n```",
        "glossary": "# Glossary\n\n- **Foo** — a test term.",
        "module_names": ["foo"],
    }


def _assert_completed(result, calls, criterion_id):
    assert result is not None
    assert field(result, "model_call_error") is None
    assert field(result, "criterion_id") == criterion_id
    assert len(calls) >= 1
    f = field(result, "file")
    assert f is not None
    content = field(f, "content")
    assert isinstance(content, str)
    assert body(content) == EXPECTED_BODY


def test_object_bundle_without_dependency_interfaces_attribute(tmp_path):
    bundle = PlainBundle("AC-FOO-001")
    assert not hasattr(bundle, "dependency_interfaces")
    assert not isinstance(bundle, dict)
    calls = []
    try:
        result = test_author.author_test(
            bundle,
            "mock-model",
            0,
            repo_root=tmp_path,
            llm_backend=make_backend(calls),
        )
    except AttributeError as exc:  # pragma: no cover - failure path
        pytest.fail("author_test raised AttributeError: " + repr(exc))
    _assert_completed(result, calls, "AC-FOO-001")


def test_dict_bundle_missing_dependency_interfaces_key(tmp_path):
    bundle = dict_bundle("AC-FOO-002")
    assert "dependency_interfaces" not in bundle
    calls = []
    try:
        result = test_author.author_test(
            bundle,
            "mock-model",
            0,
            repo_root=tmp_path,
            llm_backend=make_backend(calls),
        )
    except KeyError as exc:  # pragma: no cover - failure path
        pytest.fail("author_test raised KeyError: " + repr(exc))
    _assert_completed(result, calls, "AC-FOO-002")