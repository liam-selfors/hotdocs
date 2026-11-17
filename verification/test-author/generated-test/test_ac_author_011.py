# hotdocs-criterion: sha256:b047ca0bf3500ca9998eeef0fe2f562d9350a675d9e406cffea7bd79d7fc9c90
import re

import test_author


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


class Bundle(dict):
    """A CriterionBundle readable both as a mapping and by attribute."""

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)


def make_bundle(dependency_interfaces):
    return Bundle(
        component_id="comp-widget-maker",
        criterion_id="AC-WIDGET-MAKER-001",
        covers="R-WIDGET-MAKER-001",
        criterion_text=(
            "Given a widget spec\n"
            "When make_widget(spec) is called\n"
            "Then it returns a widget"
        ),
        requirement_text=(
            "**R-WIDGET-MAKER-001** \u2014 `make_widget(spec)` MUST return a widget."
        ),
        interface="# Library\n\n```\nmake_widget(spec: dict) -> dict\n```\n",
        glossary="# Glossary\n\n- **Widget** \u2014 a test term.\n",
        dependency_interfaces=dict(dependency_interfaces),
    )


NONCE_RE = re.compile(r"-----BEGIN FILE ([0-9a-f]{32})-----")


def make_mock(prompts):
    def backend(prompt, model, **params):
        prompts.append(prompt)
        match = NONCE_RE.search(prompt)
        nonce = match.group(1) if match else ""
        text = (
            "-----BEGIN FILE " + nonce + "-----\n"
            "import widget_maker\n\n\n"
            "def test_placeholder():\n"
            "    assert widget_maker is not None\n"
            "-----END FILE " + nonce + "-----"
        )
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    return backend


def test_dependency_interface_and_fake_rule_in_prompt(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    prompts = []
    bundle = make_bundle(
        {"comp-zebra-quux": "zq_lookup(x: int, y: str) -> ZqResult"}
    )
    test_author.author_test(
        bundle, "mock", repo_root=repo_root, llm_backend=make_mock(prompts)
    )
    assert prompts, "the mock model was never called"
    first = prompts[0]
    assert "comp-zebra-quux" in first
    assert "zq_lookup(x: int, y: str) -> ZqResult" in first
    assert (
        "a fake MUST return every field, never a bare list, string or number in its place"
        in first
    )


def test_empty_dependency_interfaces_adds_no_entry(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    prompts = []
    bundle = make_bundle({})
    result = test_author.author_test(
        bundle, "mock", repo_root=repo_root, llm_backend=make_mock(prompts)
    )
    assert field(result, "model_call_error") is None
    assert prompts, "the mock model was never called"
    assert "comp-zebra-quux" not in prompts[0]