# hotdocs-criterion: sha256:701c0fd9c94fcc19e8be7fb082233a6d4ab1de66d776c968d194d86a02cdb754
import re

import test_author


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


NONCE_RE = re.compile(r"-----BEGIN FILE ([0-9a-f]{32})-----")

TEST_BODY = (
    "import widget_maker\n"
    "\n"
    "\n"
    "def test_make_widget():\n"
    "    assert widget_maker.make_widget(2) == 4\n"
)


def make_mock():
    prompts = []

    def backend(prompt, model, **params):
        prompts.append(prompt)
        match = NONCE_RE.search(prompt)
        nonce = match.group(1) if match else "0" * 32
        text = (
            "-----BEGIN FILE " + nonce + "-----\n"
            + TEST_BODY
            + "-----END FILE " + nonce + "-----"
        )
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    return backend, prompts


def test_prompt_holds_dual_access_block(tmp_path):
    backend, prompts = make_mock()
    bundle = make_bundle()

    result = test_author.author_test(
        bundle, "mock", repo_root=tmp_path, llm_backend=backend
    )

    assert result is not None
    assert field(result, "model_call_error") is None
    assert len(prompts) >= 1

    first = prompts[0]
    expected_line = (
        "        return value[name] if isinstance(value, dict) "
        "else getattr(value, name)"
    )
    assert expected_line in first.splitlines()
    assert "MUST use dual dict-or-attribute access, never one assumed shape:" in first