import re
from pathlib import Path

import pytest

import test_author


class _Bundle(dict):
    """A CriterionBundle stand-in readable both as a mapping and by attribute."""

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)


_NONCE_RE = re.compile(r"-----BEGIN FILE ([0-9a-fA-F]+)-----")


def _make_bundle(component_id, criterion_id, covers):
    return _Bundle(
        component_id=component_id,
        criterion_id=criterion_id,
        covers=covers,
        criterion_text=(
            "Given x = 2\n"
            "When run(x) is called\n"
            "Then it returns 4\n"
        ),
        requirement_text=(
            "# " + covers + "\n\n"
            "**" + covers + "** — `run(x)` MUST return `2 * x`."
        ),
        interface="# Library\n\n```\nrun(x: int) -> int\n```\n",
        glossary="# Glossary\n\n- **Foo** — a test term.\n",
        dependency_interfaces={},
    )


def _capture_prompt(tmp_path, monkeypatch, bundle):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    workdir = tmp_path / "work"
    workdir.mkdir()
    monkeypatch.chdir(workdir)
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)

    prompt_log = tmp_path / "prompts.log"
    prompts = []

    def backend(prompt, model, **params):
        prompts.append(prompt)
        with open(prompt_log, "a", encoding="utf-8") as fh:
            fh.write(prompt)
            fh.write("\n=====END-OF-PROMPT=====\n")
        m = _NONCE_RE.search(prompt)
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

    test_author.author_test(
        bundle,
        "claude-sonnet-5",
        0,
        repo_root=repo_root,
        llm_backend=backend,
    )

    assert prompt_log.is_file(), "the mock llm_backend was never called"
    assert prompts, "the mock llm_backend was never called"
    return prompts[0]


def test_hyphenated_component_id_imports_underscored_slug(tmp_path, monkeypatch):
    bundle = _make_bundle("comp-foo-bar", "AC-FOO-BAR-001", "R-FOO-BAR-001")
    prompt = _capture_prompt(tmp_path, monkeypatch, bundle)

    assert re.search(r"import foo_bar\b", prompt), (
        "prompt must state the exact statement 'import foo_bar'"
    )
    assert "import comp_foo_bar" not in prompt, (
        "prompt must never instruct 'import comp_foo_bar'"
    )
    assert "import comp-foo-bar" not in prompt
    assert "import foo-bar" not in prompt


def test_single_word_component_id_imports_slug(tmp_path, monkeypatch):
    bundle = _make_bundle("comp-semver", "AC-SEMVER-001", "R-SEMVER-001")
    prompt = _capture_prompt(tmp_path, monkeypatch, bundle)

    assert re.search(r"import semver\b", prompt), (
        "prompt must state the exact statement 'import semver'"
    )
    assert "import comp_semver" not in prompt
    assert "import comp-semver" not in prompt