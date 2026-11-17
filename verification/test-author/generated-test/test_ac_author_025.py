import re
import uuid

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


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def make_bundle(component_id, slug_upper):
    token = uuid.uuid4().hex
    criterion_id = "AC-" + slug_upper + "-001"
    covers = "R-" + slug_upper + "-001"
    return Bundle(
        component_id=component_id,
        criterion_id=criterion_id,
        covers=covers,
        criterion_text=(
            "Given x = 2 (" + token + ")\n"
            "When the function is called\n"
            "Then it returns 4\n"
        ),
        requirement_text="**" + covers + "** — `f(x)` MUST return `2 * x`.",
        interface="# Library\n\n```\nf(x: int) -> int\n```\n",
        glossary="# Glossary\n\n- **Foo** — a test term.\n",
        dependency_interfaces={},
    )


def make_backend(prompts):
    def backend(prompt, model, **params):
        prompts.append(prompt)
        m = NONCE_RE.search(prompt)
        assert m is not None, "prompt carries no BEGIN FILE nonce"
        n = m.group(1)
        text = (
            "-----BEGIN FILE " + n + "-----\n"
            "def test_placeholder():\n"
            "    assert True\n"
            "-----END FILE " + n + "-----"
        )
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    return backend


def run(bundle, tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    prompts = []
    result = test_author.author_test(
        bundle,
        "claude-sonnet-5",
        0,
        repo_root=tmp_path,
        llm_backend=make_backend(prompts),
    )
    assert field(result, "model_call_error") is None
    assert prompts, "author_test never called the model backend"
    return prompts


def test_comp_foo_bar_prompt_names_import_foo_bar(tmp_path, monkeypatch):
    bundle = make_bundle("comp-foo-bar", "FOOBAR")
    prompts = run(bundle, tmp_path, monkeypatch)
    for prompt in prompts:
        assert "import foo_bar" in prompt
        assert (
            "The component under test itself needs no custom loader: "
            "a plain `import foo_bar`."
        ) in prompt.splitlines()
        assert "import comp_foo_bar" not in prompt
        assert "import comp-foo-bar" not in prompt


def test_comp_semver_prompt_names_import_semver(tmp_path, monkeypatch):
    bundle = make_bundle("comp-semver", "SEMVER")
    prompts = run(bundle, tmp_path, monkeypatch)
    for prompt in prompts:
        assert "import semver" in prompt
        assert (
            "The component under test itself needs no custom loader: "
            "a plain `import semver`."
        ) in prompt.splitlines()
        assert "import comp_semver" not in prompt