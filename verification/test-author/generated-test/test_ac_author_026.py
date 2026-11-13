import re

import pytest

import test_author


class _Bundle(dict):
    """A CriterionBundle stand-in readable both as a mapping and by attribute."""

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)


def _field(value, name):
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


_NONCE_RE = re.compile(r"BEGIN FILE ([0-9a-f]{32})")
_HEX_RE = re.compile(r"\b([0-9a-f]{32})\b")


def _make_backend(prompts):
    def backend(prompt, model, **params):
        prompts.append(prompt)
        m = _NONCE_RE.search(prompt) or _HEX_RE.search(prompt)
        nonce = m.group(1) if m else "0" * 32
        body = "def test_placeholder():\n    assert True\n"
        text = (
            "-----BEGIN FILE " + nonce + "-----\n"
            + body
            + "-----END FILE " + nonce + "-----\n"
        )
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    return backend


def _bundle(component_id, criterion_id, covers, module_names):
    return _Bundle(
        component_id=component_id,
        criterion_id=criterion_id,
        covers=covers,
        criterion_text=(
            "Given an input string\n"
            "When the function is called\n"
            "Then it returns the expected value"
        ),
        requirement_text="**" + covers + "** - The function MUST return the expected value.",
        interface="# Library\n\nThe public function takes a string and returns a string.",
        glossary="# Glossary\n\n- **Foo** - a test term.",
        dependency_interfaces={},
        module_names=module_names,
    )


def _run(tmp_path, monkeypatch, bundle):
    monkeypatch.chdir(tmp_path)
    prompts = []
    result = test_author.author_test(
        bundle,
        "claude-sonnet-5",
        0,
        repo_root=tmp_path,
        llm_backend=_make_backend(prompts),
    )
    assert prompts, "author_test never called the injected llm_backend, so no prompt was built"
    assert _field(result, "model_call_error") is None
    return prompts


def test_module_names_replace_derived_name(tmp_path, monkeypatch):
    bundle = _bundle(
        "capabilities/P-SLUGS",
        "AC-SLUGS-001",
        "R-SLUGS-001",
        ["slugify", "url_tools"],
    )
    prompts = _run(tmp_path, monkeypatch, bundle)
    prompt = prompts[0]

    assert "import slugify" in prompt
    assert "import url_tools" in prompt
    assert prompt.index("import slugify") < prompt.index("import url_tools")

    for p in prompts:
        assert "import capabilities" not in p


def test_empty_module_names_falls_back_to_derived_name(tmp_path, monkeypatch):
    bundle = _bundle(
        "comp-semver",
        "AC-SEMVER-001",
        "R-SEMVER-001",
        [],
    )
    prompts = _run(tmp_path, monkeypatch, bundle)
    prompt = prompts[0]

    assert "import semver" in prompt