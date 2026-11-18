# hotdocs-criterion: sha256:5123928a026b5c217d17398d0e0b2f4058e66e641676fc4c14ef6c3d3918c0ef
import json
import re
from pathlib import Path

import pytest

import test_author


CANONICAL_MODEL = "claude-sonnet-5"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


class _Bundle:
    """A CriterionBundle stand-in readable both by attribute and as a mapping."""

    def __init__(self, **kwargs):
        self._data = dict(kwargs)
        for k, v in kwargs.items():
            setattr(self, k, v)

    def __getitem__(self, key):
        return self._data[key]

    def get(self, key, default=None):
        return self._data.get(key, default)

    def keys(self):
        return self._data.keys()

    def items(self):
        return self._data.items()

    def __iter__(self):
        return iter(self._data)

    def __contains__(self, key):
        return key in self._data

    def __len__(self):
        return len(self._data)


def _make_bundle():
    return _Bundle(
        component_id="comp-foo",
        criterion_id="AC-FOO-001",
        covers="R-FOO-001",
        criterion_text=(
            "# AC-FOO-001\n\nCovers: R-FOO-001\nKind: generated-test\n\n"
            "```gherkin\nGiven x = 2\nWhen foo(x) is called\nThen it returns 4\n```\n"
        ),
        requirement_text="# R-FOO-001\n\n**R-FOO-001** \u2014 `foo(x)` MUST return `2 * x`.\n",
        interface="# Library\n\n```\nfoo(x: int) -> int\n```\n",
        glossary="# Glossary\n\n- **Foo** \u2014 a test term.\n",
        dependency_interfaces={},
        module_names=["foo"],
    )


def _seed_prior_generation(repo_root, model_a):
    """The Given: the generator used model A for this component's current code."""
    gen_dir = repo_root / "gen" / "foo"
    gen_dir.mkdir(parents=True, exist_ok=True)
    (gen_dir / "foo.py").write_text("def foo(x):\n    return 2 * x\n")
    provenance = {
        "component_id": "comp-foo",
        "model": model_a,
        "prompt_version": "v1",
        "spec_bundle_hash": "sha256:" + "0" * 64,
        "files": ["foo.py"],
    }
    (gen_dir / ".provenance.json").write_text(json.dumps(provenance, indent=2))


def _make_backend(log_path):
    def backend(prompt, model, **params):
        with open(log_path, "a") as fh:
            fh.write(json.dumps({"model": model}) + "\n")
        m = re.search(r"-----BEGIN FILE ([0-9a-f]{32})-----", prompt)
        nonce = m.group(1) if m else "0" * 32
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
    [
        "model-a-legacy",
        "anthropic:claude-opus-4",
        "ollama:llama3.1:8b",
        "openai:gpt-6-astra",
    ],
)
def test_author_test_calls_canonical_model_regardless_of_generator_model(tmp_path, model_a):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _seed_prior_generation(repo_root, model_a)

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

    assert log_path.is_file(), "the model backend was never called"
    calls = [json.loads(line) for line in log_path.read_text().splitlines() if line.strip()]
    assert len(calls) >= 1
    for call in calls:
        assert call["model"] == CANONICAL_MODEL
        assert call["model"] != model_a

    assert field(result, "model") == CANONICAL_MODEL