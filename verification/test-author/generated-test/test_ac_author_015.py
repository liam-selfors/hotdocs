# hotdocs-criterion: sha256:1199be166408761e7f0513187d375a0a4f71e5675e4433ba9f7eb607afc98db9
import re

import test_author


LINT_LINE = "    assert spec_linter.lint(None, repo_root).hard_failures == 0"


class Bundle(dict):
    """A CriterionBundle stand-in readable both as a mapping and by attribute."""

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)


def make_bundle(module_names=None):
    data = {
        "component_id": "comp-widget-maker",
        "criterion_id": "AC-WIDGET-MAKER-001",
        "covers": "R-WIDGET-MAKER-001",
        "criterion_text": (
            "Given a width w = 3\n"
            "When make_widget(w) is called\n"
            "Then it returns a widget of width 3"
        ),
        "requirement_text": (
            "# R-WIDGET-MAKER-001\n\n"
            "**R-WIDGET-MAKER-001** — `make_widget(w)` MUST return a widget of width `w`."
        ),
        "interface": "# Library\n\n```\nmake_widget(w: int) -> dict\n```",
        "glossary": "# Glossary\n\n- **Widget** — a test term.",
        "dependency_interfaces": {},
    }
    if module_names is not None:
        data["module_names"] = list(module_names)
    return Bundle(data)


def make_mock(recorded):
    def backend(prompt, model, **params):
        recorded.append(prompt)
        match = re.search(r"-----BEGIN FILE ([0-9a-f]{32})-----", prompt)
        nonce = match.group(1) if match else "0" * 32
        content = "import widget_maker\n\n\ndef test_placeholder():\n    assert True\n"
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


def _isolate(monkeypatch, root):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    monkeypatch.chdir(root)


def test_prompt_holds_lint_block_with_derived_module_name(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _isolate(monkeypatch, repo_root)

    recorded = []
    bundle = make_bundle()
    test_author.author_test(
        bundle, "mock", repo_root=repo_root, llm_backend=make_mock(recorded)
    )

    assert recorded, "the mock model was never called"
    prompt = recorded[0]
    lines = prompt.splitlines()
    assert "    import widget_maker" in lines
    assert LINT_LINE in lines
    assert "@MODULE@" not in prompt


def test_prompt_uses_first_module_name_when_given(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _isolate(monkeypatch, repo_root)

    recorded = []
    bundle = make_bundle(module_names=["alpha_mod", "beta_mod"])
    test_author.author_test(
        bundle, "mock", repo_root=repo_root, llm_backend=make_mock(recorded)
    )

    assert recorded, "the mock model was never called"
    prompt = recorded[0]
    lines = prompt.splitlines()
    assert "    import alpha_mod" in lines
    assert "    import widget_maker" not in lines
    assert LINT_LINE in lines
    assert "@MODULE@" not in prompt