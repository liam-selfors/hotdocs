# hotdocs-criterion: sha256:808b85e3b4936ee9ea210fca5c3d72d955285bba2c3e5dd434b99077feb2454a
import re

import pytest

import test_author


EXPECTED_LINE = (
    "- Every list-valued frontmatter field (`owners`, `depends_on`, `realizes`, "
    "`uses_var`) uses YAML flow style, such as `owners: [a, b]`, never block style "
    "(`- a` lines), which the frontmatter reader does not read as a list."
)


class Bundle(dict):
    """A CriterionBundle stand-in readable both as a mapping and by attribute."""

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def make_bundle():
    return Bundle(
        component_id="comp-widget-maker",
        criterion_id="AC-WIDGET-MAKER-001",
        covers="R-WIDGET-MAKER-001",
        criterion_text=(
            "Given w = 3\n"
            "When make_widget(w) is called\n"
            "Then it returns 6"
        ),
        requirement_text=(
            "# R-WIDGET-MAKER-001\n\n"
            "**R-WIDGET-MAKER-001** \u2014 `make_widget(w)` MUST return `2 * w`."
        ),
        interface="# Library\n\n```\nmake_widget(w: int) -> int\n```",
        glossary="# Glossary\n\n- **Widget** \u2014 a test term.",
        dependency_interfaces={},
    )


NONCE_RE = re.compile(r"-----BEGIN FILE ([0-9a-fA-F]{32})-----")
NONCE_FALLBACK_RE = re.compile(r"BEGIN FILE ([0-9A-Za-z]+)-----")


def make_mock(prompts):
    def backend(prompt, model, **params):
        prompts.append(prompt)
        match = NONCE_RE.search(prompt) or NONCE_FALLBACK_RE.search(prompt)
        nonce = match.group(1) if match else "0" * 32
        content = (
            "import widget_maker\n"
            "\n"
            "\n"
            "def test_make_widget():\n"
            "    assert widget_maker.make_widget(3) == 6\n"
        )
        text = (
            "-----BEGIN FILE " + nonce + "-----\n"
            + content
            + "-----END FILE " + nonce + "-----"
        )
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    return backend


def test_prompt_contains_flow_style_block(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    prompts = []
    backend = make_mock(prompts)

    result = test_author.author_test(
        make_bundle(), "mock", repo_root=repo_root, llm_backend=backend
    )

    assert result is not None
    assert prompts, "the mock model was never called"
    first_prompt = prompts[0]
    assert isinstance(first_prompt, str)
    assert EXPECTED_LINE in first_prompt.splitlines()