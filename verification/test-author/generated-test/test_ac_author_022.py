# hotdocs-criterion: sha256:98938c90d2f9c4f907a8ea1007194e8b1e8087238e08ae8813c82bee41305a07
import re

import test_author


EXPECTED_LINE = (
    "A test MUST NEVER assert a fake was used by reaching into `sys.modules` "
    "under a guessed key: real loaders key modules dynamically, often by "
    "`repo_root` or a hash, so any guess is unreliable."
)

NONCE_RE = re.compile(r"-----BEGIN FILE ([0-9a-f]{32})-----")


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


def test_prompt_contains_r_author_022_line(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)

    prompts = []

    def mock_backend(prompt, model, **params):
        prompts.append(prompt)
        match = NONCE_RE.search(prompt)
        nonce = match.group(1) if match else "0" * 32
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

    test_author.author_test(
        make_bundle(), "mock", repo_root=tmp_path, llm_backend=mock_backend
    )

    assert len(prompts) >= 1, "the mock model was never called"
    first_prompt = prompts[0]
    assert EXPECTED_LINE in first_prompt.splitlines()