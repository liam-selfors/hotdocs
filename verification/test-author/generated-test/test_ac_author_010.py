# hotdocs-criterion: sha256:832d1c0bdb0cb152b152b3ae1283b8dd0dd313e6b8fc334790d788d9ed262610
import re

import test_author


class _Bundle(dict):
    """A CriterionBundle stand-in that reads both as a mapping and by attribute."""

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
            "Given a widget size of 3\n"
            "When make_widget(3) is called\n"
            "Then it returns a widget of size 3"
        ),
        requirement_text=(
            "# R-WIDGET-MAKER-001\n\n"
            "**R-WIDGET-MAKER-001** \u2014 `make_widget(n)` MUST return a widget of size `n`."
        ),
        interface="# Library\n\n```\nmake_widget(n: int) -> dict\n```\n",
        glossary="# Glossary\n\n- **Widget** \u2014 a test term.\n",
        dependency_interfaces={},
    )


def test_prompt_holds_dependency_resolution_block(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    monkeypatch.chdir(tmp_path)

    prompts = []

    def mock_backend(prompt, model, **params):
        prompts.append(prompt)
        match = re.search(r"-----BEGIN FILE ([0-9a-f]{32})-----", prompt)
        nonce = match.group(1) if match else "0" * 32
        text = (
            "-----BEGIN FILE " + nonce + "-----\n"
            "import widget_maker\n"
            "\n"
            "\n"
            "def test_widget():\n"
            "    assert widget_maker is not None\n"
            "-----END FILE " + nonce + "-----"
        )
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    bundle = _make_bundle()
    result = test_author.author_test(
        bundle, "mock", repo_root=tmp_path, llm_backend=mock_backend
    )

    assert field(result, "model_call_error") is None
    assert len(prompts) >= 1, "the mock model was never called"

    lines = prompts[0].splitlines()

    assert (
        "The component under test itself needs no custom loader: a plain `import widget_maker`."
        in lines
    )
    assert (
        "A dependency is never interceptable by name-based `sys.modules` injection or `mock.patch`."
        in lines
    )

    sys_line = "        sys.modules[module_name] = module"
    exec_line = "        spec.loader.exec_module(module)"
    assert sys_line in lines
    assert exec_line in lines
    sys_index = lines.index(sys_line)
    assert exec_line in lines[sys_index + 1:], (
        "the exec_module line must occur after the sys.modules assignment line"
    )