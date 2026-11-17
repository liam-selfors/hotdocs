import re

import pytest

import test_author


NONCE_RE = re.compile(r"-----BEGIN FILE ([0-9a-f]{32})-----")


class Bundle(dict):
    """A CriterionBundle stand-in readable both as a mapping and by attribute."""

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)


def make_bundle(**extra):
    data = {
        "component_id": "comp-widget-maker",
        "criterion_id": "AC-WIDGET-MAKER-001",
        "covers": "R-WIDGET-MAKER-001",
        "criterion_text": (
            "Given a widget size of 2\n"
            "When make_widget(2) is called\n"
            "Then it returns a widget of size 2"
        ),
        "requirement_text": (
            "# R-WIDGET-MAKER-001\n\n"
            "**R-WIDGET-MAKER-001** — `make_widget(n)` MUST return a widget of size `n`."
        ),
        "interface": "# Library\n\n```\nmake_widget(n: int) -> dict\n```\n",
        "glossary": "# Glossary\n\n- **Widget** — a test term.\n",
        "dependency_interfaces": {},
    }
    data.update(extra)
    return Bundle(data)


def make_recording_backend():
    prompts = []

    def backend(prompt, model, **params):
        prompts.append(prompt)
        m = NONCE_RE.search(prompt)
        nonce = m.group(1) if m else "0" * 32
        body = "import os\n\n\ndef test_placeholder():\n    assert os is not None\n"
        text = "-----BEGIN FILE " + nonce + "-----\n" + body + "-----END FILE " + nonce + "-----"
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    return backend, prompts


@pytest.fixture(autouse=True)
def _local_cache(monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)


def test_prompt_holds_block_r_author_015_with_derived_module(tmp_path):
    backend, prompts = make_recording_backend()
    bundle = make_bundle()

    test_author.author_test(bundle, "mock", repo_root=tmp_path, llm_backend=backend)

    assert prompts, "the mock model was never called"
    lines = prompts[0].splitlines()
    assert "    import widget_maker" in lines
    assert "    assert spec_linter.lint(None, repo_root).hard_failures == 0" in lines
    assert "@MODULE@" not in prompts[0]


def test_prompt_uses_first_module_name_when_given(tmp_path):
    backend, prompts = make_recording_backend()
    bundle = make_bundle(module_names=["alpha_mod", "beta_mod"])

    test_author.author_test(bundle, "mock", repo_root=tmp_path, llm_backend=backend)

    assert prompts, "the mock model was never called"
    lines = prompts[0].splitlines()
    assert "    import alpha_mod" in lines
    assert "    import widget_maker" not in lines