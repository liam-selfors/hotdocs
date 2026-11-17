import re

import test_author


EXPECTED_LINE = (
    "- Every `requirements/` file of every fixture component has a matching "
    "`acceptance/` file with a `Covers:` tag."
)


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
            "Given a widget spec\n"
            "When make_widget(spec) is called\n"
            "Then it returns a widget"
        ),
        requirement_text=(
            "# R-WIDGET-MAKER-001\n\n"
            "**R-WIDGET-MAKER-001** \u2014 `make_widget(spec)` MUST return a widget."
        ),
        interface="# Library\n\n```\nmake_widget(spec: dict) -> dict\n```\n",
        glossary="# Glossary\n\n- **Widget** \u2014 a test term.\n",
        dependency_interfaces={},
    )


def test_prompt_contains_requirements_acceptance_rule_line(tmp_path):
    prompts = []
    nonce_re = re.compile(r"-----BEGIN FILE ([0-9a-fA-F]+)-----")

    def mock_backend(prompt, model, **params):
        prompts.append(prompt)
        match = nonce_re.search(prompt)
        nonce = match.group(1) if match else ""
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

    bundle = _make_bundle()
    test_author.author_test(
        bundle, "mock", repo_root=tmp_path, llm_backend=mock_backend
    )

    assert prompts, "the mock model was never called"
    first_prompt = prompts[0]
    assert EXPECTED_LINE in first_prompt.splitlines()