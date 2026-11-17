import json
import re

import pytest

import test_author


CANONICAL_MODEL = "anthropic:claude-sonnet-5-5"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


class _Bundle(dict):
    """A CriterionBundle readable both as a mapping and by attribute."""

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc


def _make_bundle():
    return _Bundle(
        component_id="comp-foo",
        criterion_id="AC-FOO-001",
        covers="R-FOO-001",
        criterion_text=(
            "Given x = 2\n"
            "When foo(x) is called\n"
            "Then it returns 4"
        ),
        requirement_text="**R-FOO-001** \u2014 `foo(x)` MUST return `2 * x`.",
        interface="# Library\n\n```\nfoo(x: int) -> int\n```",
        glossary="# Glossary\n\n- **Foo** \u2014 a test term.",
        dependency_interfaces={},
        module_names=["foo"],
    )


def _seed_generator_history(repo_root, model_a):
    """Simulate that `generator` produced comp-foo's current code with model A."""
    gen_dir = repo_root / "gen" / "foo"
    gen_dir.mkdir(parents=True, exist_ok=True)
    (gen_dir / "foo.py").write_text(
        "def foo(x):\n    return 2 * x\n", encoding="utf-8"
    )
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
    (gen_dir / ".provenance.json").write_text(
        json.dumps(provenance), encoding="utf-8"
    )


def _make_backend(log_path):
    test_body = (
        "import foo\n"
        "\n"
        "\n"
        "def test_foo_doubles():\n"
        "    assert foo.foo(2) == 4\n"
    )

    def backend(prompt, model, **params):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"model": model}) + "\n")
        m = re.search(r"-----BEGIN FILE ([0-9a-f]{32})-----", prompt)
        if m is None:
            m = re.search(r"\b([0-9a-f]{32})\b", prompt)
        nonce = m.group(1) if m else ""
        text = (
            "-----BEGIN FILE " + nonce + "-----\n"
            + test_body
            + "-----END FILE " + nonce + "-----"
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
    [
        "anthropic:claude-opus-5-5",
        "ollama:llama3.1:8b",
        "openai:gpt-6-astra",
        "claude-haiku-5-5",
        CANONICAL_MODEL,
    ],
)
def test_author_test_uses_canonical_model_regardless_of_generator_model(
    tmp_path, monkeypatch, model_a
):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _seed_generator_history(repo_root, model_a)

    log_path = tmp_path / "backend_calls.log"
    backend = _make_backend(log_path)

    result = test_author.author_test(
        _make_bundle(),
        CANONICAL_MODEL,
        0,
        repo_root=repo_root,
        llm_backend=backend,
    )

    assert field(result, "model_call_error") is None

    # The fresh repo_root has an empty cache, so the backend must have been called.
    assert log_path.is_file(), "the model backend was never called"
    calls = [
        json.loads(line)
        for line in log_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert calls, "the model backend was never called"

    # Every model call uses the canonical model alone, never the generator's model A.
    for call in calls:
        assert call["model"] == CANONICAL_MODEL

    # The recorded model is the canonical one too.
    assert field(result, "model") == CANONICAL_MODEL