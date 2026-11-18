# hotdocs-criterion: sha256:fb1c28b36326822d9c2bc84c710f7fe9e01d6eb87cdf2b3e44697b29c4d2fcae
import re

import test_author


RATIFIED_LINE = (
    "- A document with `status: ratified` also sets the placeholder "
    "`last_ratified_commit: 0000000`."
)
NO_YAML_LINE = (
    "- A test MUST NEVER `import yaml` or any other third-party package not "
    "already installed: it writes and parses frontmatter as plain text."
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
            "Given a widget size of 2\n"
            "When make_widget(2) is called\n"
            "Then it returns a widget of size 2"
        ),
        requirement_text=(
            "# R-WIDGET-MAKER-001\n\n"
            "**R-WIDGET-MAKER-001** \u2014 `make_widget(n)` MUST return a widget of size `n`."
        ),
        interface="# Library\n\n```\nmake_widget(n: int) -> dict\n```\n",
        glossary="# Glossary\n\n- **Widget** \u2014 a test term.\n",
        dependency_interfaces={},
    )


def test_prompt_holds_fixture_frontmatter_rules_block(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)

    prompts = []

    def mock_backend(prompt, model, **params):
        prompts.append(prompt)
        match = re.search(r"-----BEGIN FILE ([0-9a-fA-F]+)-----", prompt)
        nonce = match.group(1) if match else "0" * 32
        text = (
            "-----BEGIN FILE " + nonce + "-----\n"
            "import widget_maker\n"
            "\n"
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
        make_bundle(), "mock", repo_root=tmp_path, llm_backend=mock_backend
    )

    assert prompts, "the mock model was never called"
    assert field(result, "model_call_error") is None

    lines = prompts[0].splitlines()
    assert RATIFIED_LINE in lines
    assert NO_YAML_LINE in lines