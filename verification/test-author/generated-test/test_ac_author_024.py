# hotdocs-criterion: sha256:8c5734d641f3f23c85e33506432c6238ae799a40fdedf92790337a2c87d6afb4
import re

import test_author


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
            "Given a widget spec\n"
            "When make_widget(spec) is called\n"
            "Then it returns a widget"
        ),
        requirement_text=(
            "**R-WIDGET-MAKER-001** \u2014 `make_widget(spec)` MUST return a widget."
        ),
        interface="# Library\n\n```\nmake_widget(spec: dict) -> dict\n```\n",
        glossary="# Glossary\n\n- **Widget** \u2014 a test term.\n",
        dependency_interfaces={},
    )


NONCE_RE = re.compile(r"-----BEGIN FILE ([0-9a-f]{32})-----")

TEST_BODY = "def test_ok():\n    assert True\n"


def make_backend(prompts):
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

    return backend


def test_prompt_holds_block_r_author_024(tmp_path):
    prompts = []
    backend = make_backend(prompts)

    test_author.author_test(
        make_bundle(), "mock", repo_root=tmp_path, llm_backend=backend
    )

    assert prompts, "the mock model was never called"
    first = prompts[0]
    assert (
        "the fake's own code appends one line per call to a log file at a path the test controls"
        in first
    )
    assert (
        "never with `str.format`, `%` or an f-string over text that holds braces or percent signs."
        in first
    )