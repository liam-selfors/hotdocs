import re

import test_author


class _Bundle(dict):
    """A CriterionBundle stand-in readable both as a mapping and by attribute."""

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


CRITERION_TEXT = (
    "Given x = 2\n"
    "When make_widget(x) is called\n"
    "Then it returns 4"
)

REQUIREMENT_TEXT = (
    "# R-WIDGET-MAKER-001\n"
    "\n"
    "**R-WIDGET-MAKER-001** \u2014 `make_widget(x)` MUST return `2 * x`."
)

INTERFACE_TEXT = (
    "# Library\n"
    "\n"
    "```\n"
    "make_widget(x: int) -> int\n"
    "```\n"
)

GLOSSARY_TEXT = "# Glossary\n\n- **Widget** \u2014 a test term.\n"


def _make_bundle():
    return _Bundle(
        component_id="comp-widget-maker",
        criterion_id="AC-WIDGET-MAKER-001",
        covers="R-WIDGET-MAKER-001",
        criterion_text=CRITERION_TEXT,
        requirement_text=REQUIREMENT_TEXT,
        interface=INTERFACE_TEXT,
        glossary=GLOSSARY_TEXT,
        dependency_interfaces={},
    )


VALID_TEST_FILE = (
    "import widget_maker\n"
    "\n"
    "\n"
    "def test_doubles():\n"
    "    assert widget_maker.make_widget(2) == 4\n"
)


def test_prompt_holds_dual_access_block(tmp_path):
    prompts = []

    def mock_backend(prompt, model, **params):
        prompts.append(prompt)
        match = re.search(r"-----BEGIN FILE ([0-9a-fA-F]+)-----", prompt)
        nonce = match.group(1) if match else "0" * 32
        text = (
            "-----BEGIN FILE " + nonce + "-----\n"
            + VALID_TEST_FILE
            + "\n-----END FILE " + nonce + "-----"
        )
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    bundle = _make_bundle()
    result = test_author.author_test(
        bundle, "mock", repo_root=tmp_path, llm_backend=mock_backend
    )

    assert result is not None
    assert prompts, "the mock model was never called"

    first = prompts[0]
    expected_line = (
        "        return value[name] if isinstance(value, dict) else getattr(value, name)"
    )
    assert expected_line in first.splitlines()
    assert "MUST use dual dict-or-attribute access, never one assumed shape:" in first