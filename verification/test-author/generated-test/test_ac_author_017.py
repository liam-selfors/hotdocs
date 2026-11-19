# hotdocs-criterion: sha256:2b035f8dbdc356ce0cb8e88a854be98c8cd1bdf16afac2f3fa71b4ae308c7699
import re
import types

import pytest

import test_author


NONCE_RE = re.compile(r"-----BEGIN FILE ([0-9a-f]{32})-----")

EXPECTED_BODY = "import foo\n\n\ndef test_foo():\n    assert foo.foo(2) == 4"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def body(content):
    first, _, rest = content.partition("\n")
    return rest if first.startswith("# hotdocs-criterion:") else content


BASE_FIELDS = {
    "component_id": "comp-foo",
    "criterion_id": "AC-FOO-001",
    "covers": "R-FOO-001",
    "criterion_text": "Given x = 2\nWhen foo(x) is called\nThen it returns 4",
    "requirement_text": "**R-FOO-001** — `foo(x)` MUST return `2 * x`.",
    "interface": "# Library\n\n```\nfoo(x: int) -> int\n```",
    "glossary": "# Glossary\n\n- **Foo** — a test term.",
    "module_names": ["foo"],
}


def make_backend(prompts):
    def backend(prompt, model, **params):
        prompts.append(prompt)
        nonces = NONCE_RE.findall(prompt)
        assert nonces, "prompt carries no BEGIN FILE nonce"
        n = nonces[-1]
        text = "-----BEGIN FILE " + n + "-----\n" + EXPECTED_BODY + "\n-----END FILE " + n + "-----"
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    return backend


def normalize(prompt, repo_root):
    prompt = re.sub(r"[0-9a-f]{32}", "<NONCE>", prompt)
    return prompt.replace(str(repo_root), "<ROOT>")


def run(bundle, repo_root):
    prompts = []
    result = test_author.author_test(
        bundle,
        "claude-sonnet-5",
        0,
        repo_root=repo_root,
        llm_backend=make_backend(prompts),
    )
    return result, prompts


def assert_completed(result):
    assert result is not None
    assert field(result, "model_call_error") is None
    f = field(result, "file")
    assert f is not None
    assert body(field(f, "content")) == EXPECTED_BODY


def baseline_prompt(tmp_path):
    root = tmp_path / "baseline"
    root.mkdir()
    bundle = dict(BASE_FIELDS)
    bundle["dependency_interfaces"] = {}
    result, prompts = run(bundle, root)
    assert_completed(result)
    assert len(prompts) == 1
    return normalize(prompts[0], root)


def test_object_bundle_without_dependency_interfaces_attribute(tmp_path):
    root = tmp_path / "obj"
    root.mkdir()
    bundle = types.SimpleNamespace(**BASE_FIELDS)
    assert not hasattr(bundle, "dependency_interfaces")
    assert not isinstance(bundle, dict)

    try:
        result, prompts = run(bundle, root)
    except AttributeError as exc:  # pragma: no cover - failure path
        pytest.fail("author_test raised AttributeError: " + repr(exc))

    assert_completed(result)
    assert len(prompts) == 1
    assert normalize(prompts[0], root) == baseline_prompt(tmp_path)


def test_dict_bundle_without_dependency_interfaces_key(tmp_path):
    root = tmp_path / "dict"
    root.mkdir()
    bundle = dict(BASE_FIELDS)
    assert "dependency_interfaces" not in bundle

    try:
        result, prompts = run(bundle, root)
    except KeyError as exc:  # pragma: no cover - failure path
        pytest.fail("author_test raised KeyError: " + repr(exc))

    assert_completed(result)
    assert len(prompts) == 1
    assert normalize(prompts[0], root) == baseline_prompt(tmp_path)