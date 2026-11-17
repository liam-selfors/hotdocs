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


def test_prompt_holds_dependency_resolution_block(tmp_path):
    prompts = []

    def backend(prompt, model, **params):
        prompts.append(prompt)
        m = re.search(r"-----BEGIN FILE ([0-9a-f]+)-----", prompt)
        nonce = m.group(1) if m else ""
        text = (
            "-----BEGIN FILE " + nonce + "-----\n"
            "import widget_maker\n"
            "\n"
            "def test_x():\n"
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
        _make_bundle(), "mock", repo_root=tmp_path, llm_backend=backend
    )

    assert prompts, "the mock model was never called"
    lines = prompts[0].splitlines()

    assert (
        "The component under test itself needs no custom loader: a plain `import widget_maker`."
        in lines
    )
    assert (
        "A dependency is never interceptable by name-based `sys.modules` injection or `mock.patch`."
        in lines
    )

    register = "        sys.modules[module_name] = module"
    execute = "        spec.loader.exec_module(module)"
    assert register in lines
    assert execute in lines
    assert lines.index(register) < lines.index(execute)