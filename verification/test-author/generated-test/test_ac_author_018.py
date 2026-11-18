# hotdocs-criterion: sha256:ae091f478ed0e2402e73c9516912bbf0b101d4c59f0c47fe9d09f211d6c6ddfd
import re

import test_author


EXPECTED_LINE = (
    "- A unit file (`constraints.md`, or anything under `requirements/`, "
    "`interface/` or `acceptance/`) carries no frontmatter at all."
)


class _Bundle(dict):
    """A CriterionBundle stand-in readable both as a mapping and by attribute."""

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _make_bundle():
    return _Bundle(
        component_id="comp-widget-maker",
        criterion_id="AC-WIDGET-MAKER-001",
        covers="R-WIDGET-MAKER-001",
        criterion_text=(
            "Given w = 2\n"
            "When make_widget(w) is called\n"
            "Then it returns 4\n"
        ),
        requirement_text=(
            "# R-WIDGET-MAKER-001\n\n"
            "**R-WIDGET-MAKER-001** \u2014 `make_widget(w)` MUST return `2 * w`.\n"
        ),
        interface="# Library\n\n```\nmake_widget(w: int) -> int\n```\n",
        glossary="# Glossary\n\n- **Widget** \u2014 a test term.\n",
        dependency_interfaces={},
        module_names=["widget_maker"],
    )


_NONCE_RE = re.compile(r"-----BEGIN FILE ([0-9a-f]{32})-----")

_TEST_FILE = (
    "import widget_maker\n"
    "\n"
    "\n"
    "def test_make_widget():\n"
    "    assert widget_maker.make_widget(2) == 4\n"
)


def test_first_prompt_contains_unit_file_frontmatter_rule(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    prompts = []

    def mock_backend(prompt, model, **params):
        prompts.append(prompt)
        match = _NONCE_RE.search(prompt)
        nonce = match.group(1) if match else "0" * 32
        text = (
            "-----BEGIN FILE " + nonce + "-----\n"
            + _TEST_FILE
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
        bundle, "mock", repo_root=repo_root, llm_backend=mock_backend
    )

    assert result is not None
    assert field(result, "model_call_error") is None
    assert len(prompts) >= 1, "the mock model was never called"

    first_prompt = prompts[0]
    assert EXPECTED_LINE in first_prompt.splitlines()