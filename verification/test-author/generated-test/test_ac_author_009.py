import re
from pathlib import Path

import pytest

import test_author


NONCE_RE = re.compile(r"-----BEGIN FILE ([0-9a-f]+)-----")

MODEL = "claude-sonnet-5"

EXPECTED_CODE = (
    "import foo\n"
    "\n"
    "\n"
    "def test_foo_doubles():\n"
    "    assert foo.foo(2) == 4"
)

NARRATION_BEFORE = "Sure! Here is the test file you asked for:"
NARRATION_AFTER = "Let me know if you need anything else."


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def body(content):
    first, _, rest = content.partition("\n")
    return rest if first.startswith("# hotdocs-criterion:") else content


class Bundle(dict):
    """A CriterionBundle stand-in readable both as a mapping and by attribute."""

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)


def make_bundle():
    return Bundle(
        component_id="comp-foo",
        criterion_id="AC-FOO-003",
        covers="R-FOO-003",
        criterion_text=(
            "Given x = 2\n"
            "When foo(x) is called\n"
            "Then it returns 4"
        ),
        requirement_text="**R-FOO-003** — `foo(x)` MUST return `2 * x`.",
        interface="# Library\n\n```\nfoo(x: int) -> int\n```",
        glossary="# Glossary\n\n- **Foo** — a test term.",
        dependency_interfaces={},
        module_names=["foo"],
    )


def nonce_from(prompt):
    m = NONCE_RE.search(prompt)
    assert m is not None, "prompt carries no BEGIN FILE nonce marker"
    return m.group(1)


def make_fenced_backend():
    def backend(prompt, model, **params):
        n = nonce_from(prompt)
        text = (
            NARRATION_BEFORE + "\n"
            "```python\n"
            "-----BEGIN FILE " + n + "-----\n"
            + EXPECTED_CODE + "\n"
            "-----END FILE " + n + "-----\n"
            "```\n"
            + NARRATION_AFTER + "\n"
        )
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    return backend


def make_nonconforming_backend():
    def backend(prompt, model, **params):
        text = (
            NARRATION_BEFORE + "\n"
            "```python\n"
            + EXPECTED_CODE + "\n"
            "```\n"
            + NARRATION_AFTER + "\n"
        )
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    return backend


def all_files(root):
    root = Path(root)
    if not root.exists():
        return []
    return [p for p in root.rglob("*") if p.is_file()]


@pytest.fixture(autouse=True)
def _local_cache(monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)


def test_extracts_exactly_between_markers(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    result = test_author.author_test(
        make_bundle(), MODEL, 0,
        repo_root=repo_root, llm_backend=make_fenced_backend(),
    )

    assert field(result, "model_call_error") is None
    file = field(result, "file")
    assert file is not None
    content = field(file, "content")

    assert body(content) == EXPECTED_CODE
    assert "```" not in content
    assert NARRATION_BEFORE not in content
    assert NARRATION_AFTER not in content
    assert "BEGIN FILE" not in content
    assert "END FILE" not in content

    path = Path(field(file, "path"))
    written = path if path.is_absolute() else repo_root / path
    assert written.is_file()
    assert body(written.read_text()) == EXPECTED_CODE


def test_missing_markers_is_distinct_failure_and_writes_nothing(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    result = test_author.author_test(
        make_bundle(), MODEL, 0,
        repo_root=repo_root, llm_backend=make_nonconforming_backend(),
    )

    assert field(result, "file") is None
    assert field(result, "cache_hit") is False

    gen_test_dir = repo_root / "verification" / "foo" / "generated-test"
    assert all_files(gen_test_dir) == []
    assert all_files(repo_root / "verification") == []
    assert all_files(repo_root / ".hotdocs" / "cache") == []

    # Nothing was cached: a later conforming call on the same key is a
    # fresh model call, not a cache hit.
    again = test_author.author_test(
        make_bundle(), MODEL, 0,
        repo_root=repo_root, llm_backend=make_fenced_backend(),
    )
    assert field(again, "cache_hit") is False
    again_file = field(again, "file")
    assert again_file is not None
    assert body(field(again_file, "content")) == EXPECTED_CODE