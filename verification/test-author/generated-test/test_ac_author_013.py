"""AC-AUTHOR-013 (covers R-AUTHOR-013).

Given any bundle
When author_test builds its prompt
Then the prompt states that a synthetic fixture should default to
  sealed: true with a non-gen/ source_path unless the criterion under
  test specifically concerns realizes or capability-linkage behavior,
  in which case realizes must instead name at least one real P-id
"""

import json
import re
from pathlib import Path

import pytest

import test_author


class _Bundle(dict):
    """Reads both as a mapping and through attributes, like CriterionBundle."""

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc


_INTERFACE_FOO = "# Library\n\n```\nfoo(x: int) -> int\n```\n"
_GLOSSARY = "# Glossary\n\n- **Foo** — a test term."


def _bundle_plain():
    return _Bundle(
        component_id="comp-foo",
        criterion_id="AC-FOO-001",
        covers="R-FOO-001",
        criterion_text=(
            "```gherkin\nGiven x = 2\nWhen foo(x) is called\nThen it returns 4\n```"
        ),
        requirement_text="# R-FOO-001\n\n**R-FOO-001** — `foo(x)` MUST return `2 * x`.",
        interface=_INTERFACE_FOO,
        glossary=_GLOSSARY,
        dependency_interfaces={},
    )


def _bundle_with_dependency():
    return _Bundle(
        component_id="comp-bar",
        criterion_id="AC-BAR-007",
        covers="R-BAR-007",
        criterion_text=(
            "```gherkin\nGiven a bar value of 3\nWhen bar(3) is called\n"
            "Then it returns foo(3) + 1\n```"
        ),
        requirement_text=(
            "# R-BAR-007\n\n**R-BAR-007** — `bar(x)` MUST return `foo(x) + 1`."
        ),
        interface="# Library\n\n```\nbar(x: int) -> int\n```\n",
        glossary=_GLOSSARY,
        dependency_interfaces={"comp-foo": _INTERFACE_FOO},
        module_names=["bar"],
    )


_NONCE_RE = re.compile(r"-----BEGIN FILE ([0-9a-f]{32})-----")
_ANY_HEX32_RE = re.compile(r"\b([0-9a-f]{32})\b")


def _make_backend(log_path: Path, criterion_id: str):
    def backend(prompt, model, **params):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"prompt": prompt, "model": model}) + "\n")
        m = _NONCE_RE.search(prompt)
        nonce = m.group(1) if m else None
        if nonce is None:
            m2 = _ANY_HEX32_RE.search(prompt)
            nonce = m2.group(1) if m2 else "0" * 32
        body = (
            "def test_placeholder():\n"
            "    assert True  # " + criterion_id + "\n"
        )
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


def _field(value, name):
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def _read_prompts(log_path: Path):
    if not log_path.is_file():
        return []
    prompts = []
    for line in log_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            prompts.append(json.loads(line)["prompt"])
    return prompts


def _assert_sealed_default_guidance(prompt: str):
    lower = prompt.lower()

    # The individual elements must all be present somewhere.
    assert "synthetic" in lower and "fixture" in lower, (
        "prompt never mentions synthetic fixtures"
    )
    assert re.search(r"sealed:\s*true", prompt), (
        "prompt never states `sealed: true` as the fixture default"
    )
    assert "source_path" in prompt, "prompt never mentions source_path"
    assert "gen/" in prompt, "prompt never says source_path must not be under gen/"
    assert "realizes" in prompt, "prompt never mentions realizes"
    assert re.search(r"\bP-", prompt), "prompt never mentions a P-<id>"

    # And they must be stated together, as one instruction: some occurrence
    # of `sealed: true` has every other element nearby.
    window = 2500
    found = False
    for m in re.finditer(r"sealed:\s*true", prompt):
        start = max(0, m.start() - window)
        end = min(len(prompt), m.end() + window)
        chunk = prompt[start:end]
        chunk_lower = chunk.lower()
        if (
            "source_path" in chunk
            and "gen/" in chunk
            and "realizes" in chunk
            and re.search(r"\bP-", chunk)
            and "default" in chunk_lower
            and "fixture" in chunk_lower
        ):
            found = True
            break
    assert found, (
        "prompt does not state, as one instruction, that a synthetic fixture "
        "should default to `sealed: true` with a non-gen/ source_path unless "
        "the criterion concerns realizes/capability linkage, in which case it "
        "must supply a real P-<id>"
    )


@pytest.mark.parametrize(
    "make_bundle", [_bundle_plain, _bundle_with_dependency], ids=["plain", "with-dep"]
)
def test_prompt_states_sealed_default_for_synthetic_fixtures(
    tmp_path, monkeypatch, make_bundle
):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    workdir = tmp_path / "work"
    workdir.mkdir()
    monkeypatch.chdir(workdir)

    log_path = tmp_path / "backend_calls.jsonl"
    bundle = make_bundle()
    backend = _make_backend(log_path, bundle["criterion_id"])

    result = test_author.author_test(
        bundle,
        "claude-sonnet-5",
        0,
        repo_root=repo_root,
        llm_backend=backend,
    )

    prompts = _read_prompts(log_path)
    assert prompts, "author_test never called the injected llm_backend"

    assert _field(result, "model_call_error") is None, (
        "unexpected model_call_error: %r" % (_field(result, "model_call_error"),)
    )

    for prompt in prompts:
        assert isinstance(prompt, str) and prompt
        _assert_sealed_default_guidance(prompt)