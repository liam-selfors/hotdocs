# hotdocs-criterion: sha256:357cd8450846c100bc760204a36987d478df48cfb7aaba4ce09f73202a1c0760
import re
from pathlib import Path

import pytest

import test_author


NONCE_RE = re.compile(r"-----BEGIN FILE ([0-9a-fA-F]+)-----")

TEST_CODE = (
    "import os\n"
    "\n"
    "\n"
    "def test_something():\n"
    "    assert os.sep"
)


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


def make_backend(log_path, reply_for_nonce):
    def backend(prompt, model, **params):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write("call\n")
        m = NONCE_RE.search(prompt)
        nonce = m.group(1) if m else "nononce"
        return {
            "text": reply_for_nonce(nonce),
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    return backend


def read_calls(log_path):
    if not log_path.exists():
        return 0
    return len([ln for ln in log_path.read_text(encoding="utf-8").splitlines() if ln.strip()])


def cache_files(repo_root):
    cache_dir = repo_root / ".hotdocs" / "cache"
    if not cache_dir.exists():
        return []
    return [p for p in cache_dir.rglob("*") if p.is_file()]


def generated_test_files(repo_root):
    out_dir = repo_root / "verification" / "foo" / "generated-test"
    if not out_dir.exists():
        return []
    return [p for p in out_dir.rglob("*") if p.is_file()]


@pytest.fixture
def env(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    monkeypatch.chdir(repo_root)
    return repo_root, log_dir / "calls.log"


def test_extracts_strictly_between_markers_discarding_fence_and_narration(env):
    repo_root, log_path = env

    def reply(nonce):
        return (
            "Sure! Here is the test file you asked for.\n"
            "```python\n"
            + "-----BEGIN FILE " + nonce + "-----\n"
            + TEST_CODE
            + "\n-----END FILE " + nonce + "-----\n"
            + "```\n"
            + "Let me know if you need anything else.\n"
        )

    result = test_author.author_test(
        make_bundle(),
        "mock-model",
        seed=0,
        repo_root=repo_root,
        llm_backend=make_backend(log_path, reply),
    )

    assert read_calls(log_path) >= 1
    assert field(result, "model_call_error") is None
    file_value = field(result, "file")
    assert file_value is not None
    content = field(file_value, "content")

    extracted = body(content)
    assert extracted == TEST_CODE
    assert "```" not in extracted
    assert "Sure! Here is" not in extracted
    assert "Let me know" not in extracted
    assert "-----BEGIN FILE" not in extracted
    assert "-----END FILE" not in extracted

    written = generated_test_files(repo_root)
    assert len(written) == 1
    assert body(written[0].read_text(encoding="utf-8")) == TEST_CODE


def test_no_marker_pair_is_distinct_failure_with_nothing_written(env):
    repo_root, log_path = env

    def bad_reply(nonce):
        return (
            "Here is the test:\n"
            "```python\n"
            + TEST_CODE
            + "\n```\n"
            + "Hope this helps.\n"
        )

    result = test_author.author_test(
        make_bundle(),
        "mock-model",
        seed=0,
        repo_root=repo_root,
        llm_backend=make_backend(log_path, bad_reply),
    )

    assert read_calls(log_path) == 1
    assert field(result, "file") is None
    assert field(result, "cache_hit") is False

    assert generated_test_files(repo_root) == []
    assert cache_files(repo_root) == []

    # Nothing was cached: an identical follow-up call must reach the model
    # again rather than being served from cache.
    def good_reply(nonce):
        return (
            "-----BEGIN FILE " + nonce + "-----\n"
            + TEST_CODE
            + "\n-----END FILE " + nonce + "-----"
        )

    second = test_author.author_test(
        make_bundle(),
        "mock-model",
        seed=0,
        repo_root=repo_root,
        llm_backend=make_backend(log_path, good_reply),
    )

    assert read_calls(log_path) == 2
    assert field(second, "cache_hit") is False
    second_file = field(second, "file")
    assert second_file is not None
    assert body(field(second_file, "content")) == TEST_CODE