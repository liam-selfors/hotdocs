# hotdocs-criterion: sha256:a17a1338fa65f1072fe7aecaf64c95dcc44a597b62d013a882a76247cc80438f
import re

import pytest

import test_author


NONCE_RE = re.compile(r"-----BEGIN FILE ([0-9a-f]{32})-----")


class _Bundle(dict):
    """A CriterionBundle stand-in readable both as a mapping and by attribute."""

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)


def _make_bundle(component_id, slug_upper):
    return _Bundle(
        component_id=component_id,
        criterion_id="AC-" + slug_upper + "-001",
        covers="R-" + slug_upper + "-001",
        criterion_text=(
            "Given x = 2\n"
            "When compute(x) is called\n"
            "Then it returns 4\n"
        ),
        requirement_text=(
            "# R-" + slug_upper + "-001\n\n"
            "**R-" + slug_upper + "-001** \u2014 `compute(x)` MUST return `2 * x`.\n"
        ),
        interface="# Library\n\n```\ncompute(x: int) -> int\n```\n",
        glossary="# Glossary\n\n- **Foo** \u2014 a test term.\n",
        dependency_interfaces={},
    )


def _field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _capture_prompts(bundle, repo_root):
    prompts = []

    def backend(prompt, model, **params):
        prompts.append(prompt)
        m = NONCE_RE.search(prompt)
        nonce = m.group(1) if m else "0" * 32
        text = (
            "-----BEGIN FILE " + nonce + "-----\n"
            "def test_placeholder():\n"
            "    assert True\n"
            "-----END FILE " + nonce + "-----"
        )
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    result = test_author.author_test(
        bundle,
        "mock-model",
        0,
        repo_root=repo_root,
        llm_backend=backend,
    )
    assert _field(result, "model_call_error") is None
    assert prompts, "author_test never called the model backend"
    return prompts


def test_hyphenated_component_id_imports_underscored_slug(tmp_path):
    bundle = _make_bundle("comp-foo-bar", "FOOBAR")
    prompts = _capture_prompts(bundle, tmp_path)
    for prompt in prompts:
        assert "import foo_bar" in prompt
        assert "import comp_foo_bar" not in prompt
        assert "import comp-foo-bar" not in prompt


def test_single_word_component_id_imports_slug(tmp_path):
    bundle = _make_bundle("comp-semver", "SEMVER")
    prompts = _capture_prompts(bundle, tmp_path)
    for prompt in prompts:
        assert "import semver" in prompt
        assert "import comp_semver" not in prompt