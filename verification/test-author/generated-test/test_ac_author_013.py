# hotdocs-criterion: sha256:3818c6bb5b4f6f9b1cbad0319cf82577980408db08e758de309185eae04c92fe
import re

import test_author


EXPECTED_LINE = "- Only a criterion that needs `realizes`-driven behavior has the fixture supply a resolvable `P-<id>`."


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _bundle():
    return {
        "component_id": "comp-widget-maker",
        "criterion_id": "AC-WIDGET-MAKER-001",
        "covers": "R-WIDGET-MAKER-001",
        "criterion_text": (
            "Given w = 2\n"
            "When make_widget(w) is called\n"
            "Then it returns 4\n"
        ),
        "requirement_text": "**R-WIDGET-MAKER-001** — `make_widget(w)` MUST return `2 * w`.",
        "interface": "# Library\n\n```\nmake_widget(w: int) -> int\n```\n",
        "glossary": "# Glossary\n\n- **Widget** — a test term.\n",
        "dependency_interfaces": {},
    }


def test_prompt_contains_r_author_013_realizes_line(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    prompts = []

    def mock_backend(prompt, model, **params):
        prompts.append(prompt)
        match = re.search(r"-----BEGIN FILE ([0-9a-f]+)-----", prompt)
        nonce = match.group(1) if match else "0" * 32
        text = (
            "-----BEGIN FILE " + nonce + "-----\n"
            "import widget_maker\n"
            "\n"
            "\n"
            "def test_make_widget():\n"
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
        _bundle(), "mock", repo_root=repo_root, llm_backend=mock_backend
    )

    assert field(result, "model_call_error") is None
    assert len(prompts) >= 1, "the mock model was never called"
    first_prompt = prompts[0]
    assert EXPECTED_LINE in first_prompt.splitlines()