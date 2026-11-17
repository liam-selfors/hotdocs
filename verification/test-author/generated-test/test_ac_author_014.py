import re

import test_author


EXPECTED_LINE = (
    "- Every list-valued frontmatter field (`owners`, `depends_on`, `realizes`, `uses_var`) "
    "uses YAML flow style, such as `owners: [a, b]`, never block style (`- a` lines), "
    "which the frontmatter reader does not read as a list."
)


class Bundle(dict):
    """A CriterionBundle stand-in readable both as a mapping and by attribute."""

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)


def make_bundle():
    return Bundle(
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
            "**R-WIDGET-MAKER-001** \u2014 `make_widget(w)` MUST return a widget of width `w`."
        ),
        interface="# Library\n\n```\nmake_widget(w: int) -> dict\n```",
        glossary="# Glossary\n\n- **Widget** \u2014 a test term.",
        dependency_interfaces={},
    )


def make_mock(prompts):
    def backend(prompt, model, **params):
        prompts.append(prompt)
        match = re.search(r"-----BEGIN FILE ([0-9A-Za-z]+)-----", prompt)
        nonce = match.group(1) if match else ""
        text = (
            "-----BEGIN FILE " + nonce + "-----\n"
            "def test_widget():\n"
            "    assert True\n"
            "-----END FILE " + nonce + "-----"
        )
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    return backend


def test_prompt_holds_flow_style_block(tmp_path):
    prompts = []
    bundle = make_bundle()

    test_author.author_test(
        bundle, "mock", repo_root=tmp_path, llm_backend=make_mock(prompts)
    )

    assert prompts, "the mock model was never called"
    first_prompt = prompts[0]
    assert EXPECTED_LINE in first_prompt.splitlines()