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


def _make_bundle(component_id, module_names):
    return _Bundle(
        component_id=component_id,
        criterion_id="AC-SLUG-001",
        covers="R-SLUG-001",
        criterion_text=(
            "Given the text \"Hello World\"\n"
            "When it is converted\n"
            "Then the result is \"hello-world\"\n"
        ),
        requirement_text="**R-SLUG-001** -- conversion MUST lowercase and hyphenate.",
        interface="# Library\n\n    convert(text: str) -> str\n",
        glossary="# Glossary\n\n- **Slug** -- a test term.\n",
        dependency_interfaces={},
        module_names=list(module_names),
    )


def _field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _run_and_capture(bundle, repo_root):
    prompts = []

    def backend(prompt, model, **params):
        prompts.append(prompt)
        m = re.search(r"BEGIN FILE ([0-9a-f]{32})", prompt)
        nonce = m.group(1) if m else re.search(r"[0-9a-f]{32}", prompt).group(0)
        text = (
            "-----BEGIN FILE " + nonce + "-----\n"
            "def test_placeholder():\n"
            "    assert True\n"
            "-----END FILE " + nonce + "-----"
        )
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    result = test_author.author_test(
        bundle,
        "claude-sonnet-5",
        seed=0,
        repo_root=repo_root,
        llm_backend=backend,
    )
    assert _field(result, "model_call_error") is None
    assert prompts, "the model backend was never called, so no prompt was built"
    return prompts


@pytest.fixture(autouse=True)
def _local_cache(monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)


def test_module_names_replace_derived_name_for_capability_scenario(tmp_path):
    bundle = _make_bundle("capabilities/P-SLUGS", ["slugify", "url_tools"])
    prompts = _run_and_capture(bundle, tmp_path)
    for prompt in prompts:
        assert "import slugify" in prompt
        assert "import url_tools" in prompt
        assert "import capabilities" not in prompt


def test_module_names_listed_in_order(tmp_path):
    bundle = _make_bundle("capabilities/P-SLUGS", ["slugify", "url_tools"])
    prompt = _run_and_capture(bundle, tmp_path)[0]
    first_slugify = prompt.find("import slugify\n")
    if first_slugify == -1:
        first_slugify = prompt.find("import slugify")
    first_url_tools = prompt.find("import url_tools")
    assert first_slugify != -1 and first_url_tools != -1


def test_empty_module_names_falls_back_to_derived_name(tmp_path):
    bundle = _make_bundle("comp-semver", [])
    prompts = _run_and_capture(bundle, tmp_path)
    for prompt in prompts:
        assert "import semver" in prompt