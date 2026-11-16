import re
import sys

import pytest

import test_author


def _field(value, name):
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


class _Bundle(dict):
    """A CriterionBundle stand-in readable both as a mapping and by attribute."""

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)


_BUNDLE_A = {
    "component_id": "comp-foo",
    "criterion_id": "AC-FOO-001",
    "covers": "R-FOO-001",
    "criterion_text": "Given x = 2\nWhen foo(x) is called\nThen it returns 4",
    "requirement_text": "# R-FOO-001\n\n**R-FOO-001** \u2014 `foo(x)` MUST return `2 * x`.",
    "interface": "# Library\n\n```\nfoo(x: int) -> int\n```",
    "glossary": "# Glossary\n\n- **Foo** \u2014 a test term.",
    "dependency_interfaces": {},
    "module_names": ["foo"],
}

_BUNDLE_B = {
    "component_id": "comp-bar",
    "criterion_id": "AC-BAR-007",
    "covers": "R-BAR-007",
    "criterion_text": "Given an empty list\nWhen bar(items) is called\nThen it returns an empty tuple",
    "requirement_text": "# R-BAR-007\n\n**R-BAR-007** \u2014 `bar(items)` MUST return a tuple of the items.",
    "interface": "# Library\n\n```\nbar(items: list) -> tuple\n```",
    "glossary": "# Glossary\n\n- **Bar** \u2014 another test term.",
    "dependency_interfaces": {
        "comp-baz": "# Library\n\n```\nbaz(n: int) -> str\n```",
    },
}


def _make_backend(prompts):
    def backend(*args, **kwargs):
        prompt = kwargs.get("prompt")
        if prompt is None:
            prompt = args[0] if args else ""
        model = kwargs.get("model")
        if model is None:
            model = args[1] if len(args) > 1 else ""
        prompts.append(prompt)
        match = re.search(r"-----BEGIN FILE ([0-9a-fA-F]+)-----", prompt or "")
        nonce = match.group(1) if match else "0" * 32
        content = "def test_placeholder():\n    assert True\n"
        text = (
            "-----BEGIN FILE " + nonce + "-----\n"
            + content
            + "-----END FILE " + nonce + "-----\n"
        )
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    return backend


@pytest.mark.parametrize("raw_bundle", [_BUNDLE_A, _BUNDLE_B], ids=["foo", "bar"])
def test_prompt_instructs_lint_self_check_before_behavior(raw_bundle, tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    workdir = tmp_path / "cwd"
    workdir.mkdir()
    monkeypatch.chdir(workdir)

    # The bundle itself must not carry the instruction text, so anything found
    # in the prompt is the prompt's own statement, not an echo of the bundle.
    bundle_text = repr(raw_bundle).lower()
    assert "lint" not in bundle_text
    assert "hard" not in bundle_text

    prompts = []
    backend = _make_backend(prompts)
    bundle = _Bundle(raw_bundle)

    result = test_author.author_test(
        bundle,
        "claude-sonnet-5",
        0,
        repo_root=repo_root,
        llm_backend=backend,
    )

    assert _field(result, "model_call_error") is None
    assert len(prompts) >= 1, "author_test never called the model backend"

    prompt = prompts[0]
    assert isinstance(prompt, str) and prompt

    # The exact worked call shape, literally, not prose.
    assert "lint(None, repo_root)" in prompt

    lowered = prompt.lower()

    # It names spec-linter as the source of the lint() being called.
    assert re.search(r"spec[-_ ]linter", lowered), "prompt does not mention spec-linter"

    # It ties the self-check to a spec-linter-checked precondition.
    assert "precondition" in lowered, "prompt does not mention a spec-linter-checked precondition"

    # It requires asserting zero hard-fail findings.
    assert re.search(r"hard[\s_-]?fail", lowered), "prompt does not mention hard-fail findings"
    assert (
        "zero" in lowered
        or "hard_failures == 0" in prompt
        or re.search(r"==\s*0", prompt) is not None
    ), "prompt does not require zero hard-fail findings"

    # It requires the self-check to come first, before the real behavior.
    assert "before" in lowered or "first" in lowered, (
        "prompt does not require the lint self-check to run before the behavior under test"
    )

    # The snippet must not appear in a single-positional-argument form.
    assert re.search(r"lint\(\s*repo_root\s*\)", prompt) is None