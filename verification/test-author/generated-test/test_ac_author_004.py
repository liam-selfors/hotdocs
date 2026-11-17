import re
from pathlib import Path

import pytest

import test_author


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def body(content):
    first, _, rest = content.partition("\n")
    return rest if first.startswith("# hotdocs-criterion:") else content


class Bundle(dict):
    """A CriterionBundle readable both as a mapping and by attribute."""

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)


NONCE_RE = re.compile(r"-----BEGIN FILE ([0-9a-f]{32})-----")


def make_bundle():
    return Bundle(
        component_id="comp-foo",
        criterion_id="AC-FOO-001",
        covers="R-FOO-001",
        criterion_text=(
            "Given x = 2\n"
            "When foo(x) is called\n"
            "Then it returns 4"
        ),
        requirement_text="**R-FOO-001** — `foo(x)` MUST return `2 * x`.",
        interface="# Library\n\n```\nfoo(x: int) -> int\n```",
        glossary="# Glossary\n\n- **Foo** — a test term.",
        dependency_interfaces={},
        module_names=["foo"],
    )


def make_backend(log_path, file_text):
    def backend(prompt, model, **params):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write("called\n")
        m = NONCE_RE.search(prompt)
        assert m is not None, "prompt carries no BEGIN FILE nonce"
        n = m.group(1)
        text = (
            "-----BEGIN FILE " + n + "-----\n"
            + file_text
            + "\n-----END FILE " + n + "-----"
        )
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    return backend


def read_calls(log_path):
    if not log_path.exists():
        return []
    return [ln for ln in log_path.read_text(encoding="utf-8").splitlines() if ln]


def test_cached_result_returned_and_model_never_called(tmp_path, monkeypatch):
    # Use the local cache fallback under this repo_root only.
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    monkeypatch.chdir(tmp_path)

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    logs = tmp_path / "logs"
    logs.mkdir()

    model = "mock-model"
    bundle = make_bundle()

    # Pre-populate the cache for this criterion content hash and model.
    first_log = logs / "first.log"
    cached_text = "import foo\n\n\ndef test_cached():\n    assert foo.foo(2) == 4"
    first = test_author.author_test(
        bundle, model, 0,
        repo_root=repo_root,
        llm_backend=make_backend(first_log, cached_text),
    )
    assert len(read_calls(first_log)) == 1
    assert field(first, "model_call_error") is None
    assert body(field(field(first, "file"), "content")) == cached_text

    # Matching inputs again: the mock model must never be called.
    second_log = logs / "second.log"
    fresh_text = "import foo\n\n\ndef test_fresh():\n    assert False"
    second = test_author.author_test(
        make_bundle(), model, 0,
        repo_root=repo_root,
        llm_backend=make_backend(second_log, fresh_text),
    )

    assert read_calls(second_log) == [], "model was called despite a cache hit"
    assert field(second, "cache_hit") is True
    assert field(second, "model_call_error") is None
    assert field(second, "criterion_id") == "AC-FOO-001"
    assert field(second, "component_id") == "comp-foo"
    assert body(field(field(second, "file"), "content")) == cached_text