# hotdocs-criterion: sha256:5123928a026b5c217d17398d0e0b2f4058e66e641676fc4c14ef6c3d3918c0ef
import json
import re
from pathlib import Path

import pytest

import test_author


CANONICAL_MODEL = "canonical-model-zeta"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


class Bundle(dict):
    """A CriterionBundle that reads both as a mapping and by attribute."""

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)


def make_bundle():
    return Bundle(
        component_id="comp-foo",
        criterion_id="AC-FOO-001",
        covers="R-FOO-001",
        criterion_text=(
            "# AC-FOO-001\n\nCovers: R-FOO-001\nKind: generated-test\n\n"
            "```gherkin\nGiven x = 2\nWhen foo(x) is called\nThen it returns 4\n```\n"
        ),
        requirement_text="# R-FOO-001\n\n**R-FOO-001** — `foo(x)` MUST return `2 * x`.",
        interface="# Library\n\n```\nfoo(x: int) -> int\n```\n",
        glossary="# Glossary\n\n- **Foo** — a test term.",
        dependency_interfaces={},
        module_names=["foo"],
    )


def write_generator_state(repo_root, model_a):
    """Record that the generator produced this component's current code with model A."""
    gen_dir = Path(repo_root) / "gen" / "foo"
    gen_dir.mkdir(parents=True, exist_ok=True)
    (gen_dir / "foo.py").write_text("def foo(x):\n    return 2 * x\n")
    provenance = {
        "component_id": "comp-foo",
        "model": model_a,
        "generation_result": {
            "component_id": "comp-foo",
            "spec_bundle_hash": "sha256:" + "0" * 64,
            "model": model_a,
            "prompt_version": "v1",
            "cache_hit": False,
            "files": {"foo.py": "def foo(x):\n    return 2 * x\n"},
            "model_call_error": None,
            "refused": None,
            "retry_feedback": None,
        },
    }
    (gen_dir / ".provenance.json").write_text(json.dumps(provenance))


def make_backend(calls):
    def backend(prompt, model, **params):
        calls.append(model)
        match = re.search(r"-----BEGIN FILE ([0-9a-f]{32})-----", prompt)
        nonce = match.group(1) if match else "0" * 32
        text = (
            "-----BEGIN FILE " + nonce + "-----\n"
            "import foo\n\n\ndef test_foo():\n    assert foo.foo(2) == 4\n"
            "-----END FILE " + nonce + "-----"
        )
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    return backend


@pytest.mark.parametrize(
    "model_a",
    ["claude-opus-4", "openai:gpt-6-astra", "ollama:llama3.1:8b", "some-other-model"],
)
def test_author_test_uses_canonical_model_regardless_of_generator_model(
    tmp_path, monkeypatch, model_a
):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    repo_root = tmp_path / ("repo_" + re.sub(r"[^a-zA-Z0-9]", "_", model_a))
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)
    write_generator_state(repo_root, model_a)

    calls = []
    result = test_author.author_test(
        make_bundle(),
        CANONICAL_MODEL,
        0,
        repo_root=repo_root,
        llm_backend=make_backend(calls),
    )

    assert field(result, "model_call_error") is None
    assert calls, "the model backend was never called"
    for called_model in calls:
        assert called_model == CANONICAL_MODEL
        assert called_model != model_a
    assert field(result, "model") == CANONICAL_MODEL