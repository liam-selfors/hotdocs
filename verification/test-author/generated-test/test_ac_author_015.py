# hotdocs-criterion: sha256:1199be166408761e7f0513187d375a0a4f71e5675e4433ba9f7eb607afc98db9
import re

import test_author


class _Bundle(dict):
    """A CriterionBundle stand-in readable both as a mapping and by attribute."""

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)


def _make_bundle(module_names=None):
    data = {
        "component_id": "comp-widget-maker",
        "criterion_id": "AC-WIDGET-MAKER-001",
        "covers": "R-WIDGET-MAKER-001",
        "criterion_text": "Given x = 2\nWhen make(x) is called\nThen it returns 4",
        "requirement_text": "# R-WIDGET-MAKER-001\n\n**R-WIDGET-MAKER-001** — `make(x)` MUST return `2 * x`.",
        "interface": "# Library\n\n```\nmake(x: int) -> int\n```",
        "glossary": "# Glossary\n\n- **Widget** — a test term.",
        "dependency_interfaces": {},
    }
    if module_names is not None:
        data["module_names"] = list(module_names)
    return _Bundle(data)


_NONCE_RE = re.compile(r"-----BEGIN FILE ([0-9a-f]{32})-----")


def _make_backend(recorded):
    def backend(prompt, model, **params):
        recorded.append(prompt)
        match = _NONCE_RE.search(prompt)
        nonce = match.group(1) if match else "0" * 32
        text = (
            "-----BEGIN FILE " + nonce + "-----\n"
            + "def test_ok():\n    assert True\n"
            + "-----END FILE " + nonce + "-----"
        )
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    return backend


def test_prompt_holds_lint_self_check_block_with_derived_module(tmp_path):
    recorded = []
    bundle = _make_bundle()
    test_author.author_test(
        bundle, "mock", repo_root=tmp_path, llm_backend=_make_backend(recorded)
    )
    assert recorded, "the mock model was never called"
    prompt = recorded[0]
    lines = prompt.splitlines()
    assert "    import widget_maker" in lines
    assert "    assert spec_linter.lint(None, repo_root).hard_failures == 0" in lines
    assert "@MODULE@" not in prompt


def test_prompt_uses_first_module_name_when_given(tmp_path):
    recorded = []
    bundle = _make_bundle(module_names=["alpha_mod", "beta_mod"])
    test_author.author_test(
        bundle, "mock", repo_root=tmp_path, llm_backend=_make_backend(recorded)
    )
    assert recorded, "the mock model was never called"
    prompt = recorded[0]
    lines = prompt.splitlines()
    assert "    import alpha_mod" in lines
    assert "    import widget_maker" not in lines