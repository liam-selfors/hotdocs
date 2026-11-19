# hotdocs-criterion: sha256:d9634ae64bd7805e29fa8845ec396254cff614dd2ed940a679560181c2531721
import re

import test_author


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


def _find_nonce(prompt):
    m = re.search(r"-----BEGIN FILE ([0-9a-f]{32})-----", prompt)
    if m:
        return m.group(1)
    m = re.search(r"-----END FILE ([0-9a-f]{32})-----", prompt)
    if m:
        return m.group(1)
    m = re.search(r"\b([0-9a-f]{32})\b", prompt)
    assert m is not None, "no nonce found in prompt"
    return m.group(1)


def test_prompt_holds_write_time_window_precision_block(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    prompts = []

    def mock_backend(prompt, model, **params):
        prompts.append(prompt)
        nonce = _find_nonce(prompt)
        text = (
            "-----BEGIN FILE " + nonce + "-----\n"
            "import widget_maker\n"
            "\n"
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

    test_author.author_test(
        _make_bundle(), "mock", repo_root=tmp_path, llm_backend=mock_backend
    )

    assert len(prompts) >= 1
    first = prompts[0]
    assert "(`datetime.now(timezone.utc).replace(microsecond=0)`)" in first
    assert (
        "never comparing a timestamp truncated on write against "
        "microsecond-precision bounds."
    ) in first