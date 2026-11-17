import re

import test_author


EXPECTED_FAKE_LOG = (
    "the fake's own code appends one line per call to a log file "
    "at a path the test controls"
)
EXPECTED_NO_FORMAT = (
    "never with `str.format`, `%` or an f-string over text that holds "
    "braces or percent signs."
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
            "Given a widget size of 2\n"
            "When make_widget(2) is called\n"
            "Then it returns a widget of size 2"
        ),
        requirement_text=(
            "**R-WIDGET-MAKER-001** — `make_widget(size)` MUST return a "
            "widget whose size is `size`."
        ),
        interface="# Library\n\n```\nmake_widget(size: int) -> dict\n```\n",
        glossary="# Glossary\n\n- **Widget** — a test term.\n",
        dependency_interfaces={},
    )


def _make_mock(recorded):
    def backend(prompt, model, **params):
        recorded.append(prompt)
        match = re.search(r"-----BEGIN FILE ([0-9a-fA-F]+)-----", prompt)
        nonce = match.group(1) if match else ""
        text = (
            "-----BEGIN FILE " + nonce + "-----\n"
            "import widget_maker\n"
            "\n"
            "def test_placeholder():\n"
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


def test_prompt_holds_block_r_author_024(tmp_path):
    recorded = []
    backend = _make_mock(recorded)
    bundle = _make_bundle()

    test_author.author_test(
        bundle, "mock", repo_root=tmp_path, llm_backend=backend
    )

    assert len(recorded) >= 1, "the mock model was never called"
    first_prompt = recorded[0]
    assert EXPECTED_FAKE_LOG in first_prompt
    assert EXPECTED_NO_FORMAT in first_prompt