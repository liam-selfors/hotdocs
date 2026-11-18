# hotdocs-criterion: sha256:07a8aba0f528ef8eb6efeedfeea07fe06c60fea4ae2bce330eb1d1a1bd278683
import re

import test_author


REQUIRED_LINE = (
    "- Every `requirements/` file of every fixture component has a matching "
    "`acceptance/` file with a `Covers:` tag."
)

NONCE_RE = re.compile(r"-----BEGIN FILE ([0-9a-f]+)-----")


class _Bundle(dict):
    """A CriterionBundle stand-in readable both as a mapping and by attribute."""

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)


def _make_bundle():
    return _Bundle(
        component_id="comp-widget-maker",
        criterion_id="AC-WIDGET-MAKER-001",
        covers="R-WIDGET-MAKER-001",
        criterion_text=(
            "Given a width of 3\n"
            "When make_widget(3) is called\n"
            "Then it returns a widget of width 3"
        ),
        requirement_text=(
            "# R-WIDGET-MAKER-001\n\n"
            "**R-WIDGET-MAKER-001** — `make_widget(w)` MUST return a widget of width `w`."
        ),
        interface="# Library\n\n```\nmake_widget(w: int) -> dict\n```\n",
        glossary="# Glossary\n\n- **Widget** — a test term.\n",
        dependency_interfaces={},
    )


def test_prompt_contains_requirements_acceptance_rule_line(tmp_path):
    prompts = []

    def mock_backend(prompt, model=None, *args, **params):
        prompts.append(prompt)
        match = NONCE_RE.search(prompt)
        nonce = match.group(1) if match else "0" * 32
        body = (
            "import widget_maker\n"
            "\n"
            "\n"
            "def test_make_widget():\n"
            "    assert widget_maker is not None\n"
        )
        text = (
            "-----BEGIN FILE " + nonce + "-----\n"
            + body
            + "-----END FILE " + nonce + "-----"
        )
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    bundle = _make_bundle()
    test_author.author_test(
        bundle, "mock", repo_root=tmp_path, llm_backend=mock_backend
    )

    assert prompts, "the mock model was never called"
    first_prompt = prompts[0]
    assert isinstance(first_prompt, str)
    assert REQUIRED_LINE in first_prompt.splitlines()