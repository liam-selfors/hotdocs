import re

import test_author


EXPECTED_LINE = (
    "A test MUST NEVER assert a fake was used by reaching into `sys.modules` "
    "under a guessed key: real loaders key modules dynamically, often by "
    "`repo_root` or a hash, so any guess is unreliable."
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
            "**R-WIDGET-MAKER-001** — `make_widget(n)` MUST return a widget of size `n`."
        ),
        interface="# Library\n\n```\nmake_widget(n: int) -> dict\n```",
        glossary="# Glossary\n\n- **Widget** — a test term.",
        dependency_interfaces={},
    )


_NONCE_RE = re.compile(r"-----BEGIN FILE ([0-9a-fA-F]+)-----")


def test_prompt_contains_r_author_022_block_line(tmp_path):
    prompts = []

    def mock_backend(prompt, model, **params):
        prompts.append(prompt)
        match = _NONCE_RE.search(prompt)
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

    test_author.author_test(
        _make_bundle(), "mock", repo_root=tmp_path, llm_backend=mock_backend
    )

    assert prompts, "the mock model was never called"
    first_prompt = prompts[0]
    assert EXPECTED_LINE in first_prompt.splitlines()