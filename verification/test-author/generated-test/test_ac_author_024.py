# hotdocs-criterion: sha256:8c5734d641f3f23c85e33506432c6238ae799a40fdedf92790337a2c87d6afb4
import re

import test_author


LOG_LINE = (
    "the fake's own code appends one line per call to a log file at a path the test controls"
)
CONCAT_LINE = (
    "never with `str.format`, `%` or an f-string over text that holds braces or percent signs."
)

NONCE_RE = re.compile(r"-----BEGIN FILE ([0-9a-f]{32})-----")


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def make_bundle():
    return {
        "component_id": "comp-widget-maker",
        "criterion_id": "AC-WIDGET-MAKER-001",
        "covers": "R-WIDGET-MAKER-001",
        "criterion_text": (
            "Given x = 2\n"
            "When make_widget(x) is called\n"
            "Then it returns 4"
        ),
        "requirement_text": (
            "# R-WIDGET-MAKER-001\n\n"
            "**R-WIDGET-MAKER-001** — `make_widget(x)` MUST return `2 * x`."
        ),
        "interface": "# Library\n\n```\nmake_widget(x: int) -> int\n```",
        "glossary": "# Glossary\n\n- **Widget** — a test term.",
        "dependency_interfaces": {},
    }


def test_prompt_holds_block_r_author_024(tmp_path):
    prompts = []

    def mock_backend(prompt, model, **params):
        prompts.append(prompt)
        match = NONCE_RE.search(prompt)
        nonce = match.group(1) if match else ""
        text = (
            "-----BEGIN FILE " + nonce + "-----\n"
            "def test_ok():\n"
            "    assert True\n"
            "-----END FILE " + nonce + "-----"
        )
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    result = test_author.author_test(
        make_bundle(), "mock", repo_root=repo_root, llm_backend=mock_backend
    )

    assert field(result, "model_call_error") is None
    assert prompts, "the mock model was never called"

    first = prompts[0]
    assert LOG_LINE in first
    assert CONCAT_LINE in first