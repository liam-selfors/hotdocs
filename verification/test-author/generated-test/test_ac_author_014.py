# hotdocs-criterion: sha256:808b85e3b4936ee9ea210fca5c3d72d955285bba2c3e5dd434b99077feb2454a
import re

import test_author


EXPECTED_LINE = (
    "- Every list-valued frontmatter field (`owners`, `depends_on`, "
    "`realizes`, `uses_var`) uses YAML flow style, such as `owners: [a, b]`, "
    "never block style (`- a` lines), which the frontmatter reader does not "
    "read as a list."
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


def _field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def test_prompt_contains_flow_style_frontmatter_block(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)

    prompts = []

    def mock_backend(prompt, model, **params):
        prompts.append(prompt)
        match = re.search(r"-----BEGIN FILE ([0-9A-Fa-f]+)-----", prompt)
        nonce = match.group(1) if match else ""
        text = (
            "-----BEGIN FILE " + nonce + "-----\n"
            "import widget_maker\n"
            "\n"
            "def test_x():\n"
            "    assert widget_maker.make_widget(2) == 4\n"
            "-----END FILE " + nonce + "-----"
        )
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    result = test_author.author_test(
        _make_bundle(), "mock", repo_root=tmp_path, llm_backend=mock_backend
    )

    assert prompts, "the mock model was never called"
    first_prompt = prompts[0]
    assert EXPECTED_LINE in first_prompt.splitlines()

    # The call itself succeeded with the mock's valid reply.
    assert _field(result, "model_call_error") is None