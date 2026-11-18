# hotdocs-criterion: sha256:d9634ae64bd7805e29fa8845ec396254cff614dd2ed940a679560181c2531721
import re

import test_author


class Bundle(dict):
    """A CriterionBundle that reads both as a mapping and by attribute."""

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
            "# R-WIDGET-MAKER-001\n\n"
            "**R-WIDGET-MAKER-001** — `make_widget(spec)` MUST return a widget."
        ),
        interface="# Library\n\n```\nmake_widget(spec: dict) -> dict\n```",
        glossary="# Glossary\n\n- **Widget** — a test term.",
        dependency_interfaces={},
    )


NONCE_RE = re.compile(r"-----BEGIN FILE ([0-9a-f]{32})-----")


def make_mock(recorded):
    def backend(prompt, model, **params):
        recorded.append(prompt)
        match = NONCE_RE.search(prompt)
        nonce = match.group(1) if match else "0" * 32
        content = (
            "import widget_maker\n"
            "\n"
            "\n"
            "def test_widget():\n"
            "    assert widget_maker is not None\n"
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

    return backend


def test_prompt_holds_write_time_window_precision_block(tmp_path):
    recorded = []
    backend = make_mock(recorded)

    test_author.author_test(
        make_bundle(), "mock", repo_root=tmp_path, llm_backend=backend
    )

    assert len(recorded) >= 1, "the mock model was never called"
    first_prompt = recorded[0]
    assert "(`datetime.now(timezone.utc).replace(microsecond=0)`)" in first_prompt
    assert (
        "never comparing a timestamp truncated on write against "
        "microsecond-precision bounds."
    ) in first_prompt