import re

import test_author


LINE_RATIFIED = "- A document with `status: ratified` also sets the placeholder `last_ratified_commit: 0000000`."
LINE_NO_YAML = "- A test MUST NEVER `import yaml` or any other third-party package not already installed: it writes and parses frontmatter as plain text."


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
            "Given a widget size of 2\n"
            "When make_widget(2) is called\n"
            "Then it returns a widget of size 2"
        ),
        requirement_text=(
            "# R-WIDGET-MAKER-001\n\n"
            "**R-WIDGET-MAKER-001** \u2014 `make_widget(size)` MUST return a widget of that size."
        ),
        interface="# Library\n\n```\nmake_widget(size: int) -> dict\n```\n",
        glossary="# Glossary\n\n- **Widget** \u2014 a test term.\n",
        dependency_interfaces={},
    )


def _make_mock(recorded):
    nonce_re = re.compile(r"-----BEGIN FILE ([0-9a-fA-F]+)-----")

    def backend(prompt, model, **params):
        recorded.append(prompt)
        match = nonce_re.search(prompt)
        nonce = match.group(1) if match else ""
        text = (
            "-----BEGIN FILE " + nonce + "-----\n"
            "import widget_maker\n"
            "\n"
            "\n"
            "def test_widget():\n"
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


def test_ac_author_012_prompt_holds_fixture_frontmatter_block(tmp_path):
    recorded = []
    backend = _make_mock(recorded)

    test_author.author_test(
        _make_bundle(), "mock", repo_root=tmp_path, llm_backend=backend
    )

    assert recorded, "the mock model was never called"
    lines = recorded[0].splitlines()
    assert LINE_RATIFIED in lines
    assert LINE_NO_YAML in lines