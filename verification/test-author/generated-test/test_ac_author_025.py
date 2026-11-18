# hotdocs-criterion: sha256:a17a1338fa65f1072fe7aecaf64c95dcc44a597b62d013a882a76247cc80438f
import re

import pytest

import test_author


NONCE_RE = re.compile(r"-----BEGIN FILE ([0-9a-f]{32})-----")


class Bundle(dict):
    """A CriterionBundle that reads both as a mapping and by attribute."""

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)


def make_bundle(component_id, slug_upper):
    return Bundle(
        component_id=component_id,
        criterion_id="AC-" + slug_upper + "-001",
        covers="R-" + slug_upper + "-001",
        criterion_text=(
            "Given x = 2\n"
            "When run(x) is called\n"
            "Then it returns 4\n"
        ),
        requirement_text=(
            "# R-" + slug_upper + "-001\n\n"
            "**R-" + slug_upper + "-001** \u2014 `run(x)` MUST return `2 * x`.\n"
        ),
        interface="# Library\n\n```\nrun(x: int) -> int\n```\n",
        glossary="# Glossary\n\n- **Foo** \u2014 a test term.\n",
        dependency_interfaces={},
    )


def make_backend(prompts, module_name):
    def backend(prompt, model, **params):
        prompts.append(prompt)
        match = NONCE_RE.search(prompt)
        nonce = match.group(1) if match else "0" * 32
        content = (
            "import " + module_name + "\n"
            "\n"
            "def test_placeholder():\n"
            "    assert True\n"
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


def run_author(bundle, module_name, repo_root):
    prompts = []
    test_author.author_test(
        bundle,
        "claude-sonnet-5",
        0,
        repo_root=repo_root,
        llm_backend=make_backend(prompts, module_name),
    )
    assert prompts, "author_test never called the model backend"
    return prompts


def test_multi_hyphen_slug_is_imported_as_underscored_slug(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    bundle = make_bundle("comp-foo-bar", "FOOBAR")

    prompts = run_author(bundle, "foo_bar", repo_root)

    for prompt in prompts:
        assert "import foo_bar" in prompt
        assert (
            "The component under test itself needs no custom loader: a plain `import foo_bar`."
            in prompt.splitlines()
        )
        assert "import comp_foo_bar" not in prompt
        assert "import foo-bar" not in prompt


def test_single_word_slug_is_imported_as_slug(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    bundle = make_bundle("comp-semver", "SEMVER")

    prompts = run_author(bundle, "semver", repo_root)

    for prompt in prompts:
        assert "import semver" in prompt
        assert (
            "The component under test itself needs no custom loader: a plain `import semver`."
            in prompt.splitlines()
        )
        assert "import comp_semver" not in prompt