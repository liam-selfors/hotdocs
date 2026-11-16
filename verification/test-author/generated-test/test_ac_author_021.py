import re

import pytest

import test_author


MODEL = "anthropic:claude-sonnet-5"


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


def _make_bundle(suffix, criterion_num):
    crit_id = "AC-FOO%s-%03d" % (suffix, criterion_num)
    req_id = "R-FOO%s-%03d" % (suffix, criterion_num)
    return _Bundle(
        component_id="comp-foo%s" % suffix.lower(),
        criterion_id=crit_id,
        covers=req_id,
        criterion_text=(
            "# %s\n\nCovers: %s\nKind: generated-test\n\n"
            "```gherkin\nGiven x = 2\nWhen foo(x) is called\nThen it returns 4\n```\n"
            % (crit_id, req_id)
        ),
        requirement_text="# %s\n\n**%s** — `foo(x)` MUST return `2 * x`." % (req_id, req_id),
        interface="# Library\n\n```\nfoo(x: int) -> int\n```",
        glossary="# Glossary\n\n- **Foo** — a test term.",
        dependency_interfaces={},
        module_names=["foo%s" % suffix.lower()],
    )


def _make_backend(captured):
    def backend(prompt, model, **params):
        captured.append(prompt)
        match = re.search(r"-----BEGIN FILE ([0-9a-fA-F]+)-----", prompt)
        assert match is not None, "prompt carries no BEGIN FILE nonce marker"
        nonce = match.group(1)
        content = "def test_placeholder():\n    assert True\n"
        text = "-----BEGIN FILE %s-----\n%s-----END FILE %s-----\n" % (nonce, content, nonce)
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    return backend


def _chunks(prompt):
    """Split the prompt into paragraphs and list items, each joined to one line."""
    chunks = []
    for para in re.split(r"\n\s*\n", prompt):
        current = []
        for line in para.splitlines():
            if re.match(r"^\s*(?:[-*•]|\d+[.)])\s+", line) and current:
                chunks.append(" ".join(current))
                current = []
            current.append(line.strip())
        if current:
            chunks.append(" ".join(current))
    return chunks


def _has_dual_access_instruction(prompt):
    for chunk in _chunks(prompt):
        low = chunk.lower()
        mentions_dict = "dict" in low or "mapping" in low
        mentions_attr = "attribute" in low or "getattr" in low or "attr" in low
        mentions_dual = (
            "dual" in low
            or "dict-or-attribute" in low
            or ("isinstance" in low and "getattr" in low)
            or "either" in low
            or ("dict" in low and " or " in low and "attribute" in low)
        )
        mentions_return = "return" in low
        mentions_target = (
            "itself" in low
            or "under test" in low
            or "target" in low
        )
        mentions_not_one_shape = (
            "never" in low
            or "not only" in low
            or "one shape" in low
            or "either shape" in low
            or "only a dict" in low
            or "bare" in low
        )
        if (
            mentions_dict
            and mentions_attr
            and mentions_dual
            and mentions_return
            and mentions_target
            and mentions_not_one_shape
        ):
            return True
    return False


@pytest.mark.parametrize(
    "suffix,criterion_num,seed",
    [("", 1, 0), ("BAR", 7, 3)],
)
def test_prompt_instructs_dual_access_for_target_return_values(
    tmp_path, monkeypatch, suffix, criterion_num, seed
):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    work = tmp_path / "cwd"
    work.mkdir()
    monkeypatch.chdir(work)

    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    captured = []
    bundle = _make_bundle(suffix, criterion_num)

    result = test_author.author_test(
        bundle,
        MODEL,
        seed=seed,
        repo_root=repo_root,
        llm_backend=_make_backend(captured),
    )

    assert _field(result, "model_call_error") is None
    assert captured, "author_test never called the model backend with a prompt"

    prompt = captured[-1]
    assert isinstance(prompt, str) and prompt

    assert _has_dual_access_instruction(prompt), (
        "prompt does not instruct that every field read from a value the target "
        "component itself returns must use dual dict-or-attribute access"
    )