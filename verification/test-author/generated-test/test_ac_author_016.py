# hotdocs-criterion: sha256:07a8aba0f528ef8eb6efeedfeea07fe06c60fea4ae2bce330eb1d1a1bd278683
import re

import test_author


EXPECTED_LINE = (
    "- Every `requirements/` file of every fixture component has a matching "
    "`acceptance/` file with a `Covers:` tag."
)


class _Bundle(dict):
    """A CriterionBundle stand-in that reads both as a mapping and by attribute."""

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
            "Given x = 2\n"
            "When make_widget(x) is called\n"
            "Then it returns 4"
        ),
        requirement_text=(
            "# R-WIDGET-MAKER-001\n\n"
            "**R-WIDGET-MAKER-001** — `make_widget(x)` MUST return `2 * x`."
        ),
        interface="# Library\n\n```\nmake_widget(x: int) -> int\n```",
        glossary="# Glossary\n\n- **Widget** — a test term.",
        dependency_interfaces={},
    )


def test_prompt_contains_fixture_requirements_acceptance_rule_line(tmp_path):
    prompts = []

    def mock_backend(prompt, model, **params):
        prompts.append(prompt)
        match = re.search(r"-----BEGIN FILE ([0-9a-f]+)-----", prompt)
        nonce = match.group(1) if match else "0" * 32
        text = (
            "-----BEGIN FILE " + nonce + "-----\n"
            "import widget_maker\n"
            "\n"
            "\n"
            "def test_make_widget():\n"
            "    assert widget_maker.make_widget(2) == 4\n"
            "-----END FILE " + nonce + "-----"
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
    assert EXPECTED_LINE in first_prompt.splitlines()