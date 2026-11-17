import re

import test_author


class _Bundle(dict):
    """A CriterionBundle readable both as a mapping and by attribute."""

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


_NONCE_RE = re.compile(r"-----BEGIN FILE ([0-9a-f]+)-----")


def test_prompt_holds_write_time_window_precision_block(tmp_path):
    prompts = []

    def mock_backend(prompt, model, **params):
        prompts.append(prompt)
        match = _NONCE_RE.search(prompt)
        nonce = match.group(1) if match else "0" * 32
        content = (
            "import widget_maker\n\n\n"
            "def test_doubles():\n"
            "    assert widget_maker.make_widget(2) == 4\n"
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

    test_author.author_test(
        _make_bundle(), "mock", repo_root=tmp_path, llm_backend=mock_backend
    )

    assert prompts, "the mock model was never called"
    first = prompts[0]
    assert "(`datetime.now(timezone.utc).replace(microsecond=0)`)" in first
    assert (
        "never comparing a timestamp truncated on write against "
        "microsecond-precision bounds." in first
    )