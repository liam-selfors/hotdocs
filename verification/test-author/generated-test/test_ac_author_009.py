# hotdocs-criterion: sha256:357cd8450846c100bc760204a36987d478df48cfb7aaba4ce09f73202a1c0760
import re
from pathlib import Path

import pytest

import test_author


MODEL = "anthropic:claude-sonnet-5"

NONCE_RE = re.compile(r"-----BEGIN FILE ([0-9a-f]{32})-----")

REAL_CODE = (
    "import os\n"
    "\n"
    "\n"
    "def test_something():\n"
    "    assert os.path.join('a', 'b').endswith('b')"
)


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
            "Then it returns 4\n"
        ),
        requirement_text="**R-FOO-003** — `foo(x)` MUST return `2 * x`.",
        interface="# Library\n\n```\nfoo(x: int) -> int\n```\n",
        glossary="# Glossary\n\n- **Foo** — a test term.\n",
        dependency_interfaces={},
        module_names=["foo"],
    )


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def body(content):
    first, _, rest = content.partition("\n")
    return rest if first.startswith("# hotdocs-criterion:") else content


def nonce_from(prompt):
    m = NONCE_RE.search(prompt)
    assert m is not None, "prompt carries no hex nonce in a BEGIN FILE marker"
    return m.group(1)


def make_backend(log_path, reply_for_nonce):
    def backend(prompt, model, **params):
        with open(log_path, "a") as fh:
            fh.write("call\n")
        n = nonce_from(prompt)
        return {
            "text": reply_for_nonce(n),
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    return backend


def call_count(log_path):
    if not Path(log_path).is_file():
        return 0
    return len(Path(log_path).read_text().splitlines())


def files_under(path):
    path = Path(path)
    if not path.exists():
        return []
    return [p for p in path.rglob("*") if p.is_file()]


@pytest.fixture
def repo_root(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    root.mkdir()
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    monkeypatch.chdir(root)
    return root


def test_extracts_strictly_between_markers_discarding_fence_and_narration(
    repo_root, tmp_path
):
    log_path = tmp_path / "calls.log"

    def reply(n):
        return (
            "Sure, here is the test file you asked for.\n"
            "```python\n"
            "-----BEGIN FILE " + n + "-----\n"
            + REAL_CODE
            + "\n-----END FILE " + n + "-----\n"
            "```\n"
            "Let me know if you need anything else."
        )

    backend = make_backend(log_path, reply)
    result = test_author.author_test(
        make_bundle(), MODEL, 0, repo_root=repo_root, llm_backend=backend
    )

    assert call_count(log_path) == 1
    assert field(result, "model_call_error") is None
    f = field(result, "file")
    assert f is not None
    content = field(f, "content")
    extracted = body(content)

    assert extracted == REAL_CODE
    assert "```" not in extracted
    assert "BEGIN FILE" not in extracted
    assert "END FILE" not in extracted
    assert "Sure, here is" not in extracted
    assert "Let me know" not in extracted


def test_no_marker_pair_is_distinct_failure_and_nothing_persisted(
    repo_root, tmp_path
):
    log_path = tmp_path / "calls.log"

    def bad_reply(n):
        return (
            "Here is the test file:\n"
            "```python\n"
            + REAL_CODE
            + "\n```\n"
            "Done."
        )

    backend = make_backend(log_path, bad_reply)
    result = test_author.author_test(
        make_bundle(), MODEL, 0, repo_root=repo_root, llm_backend=backend
    )

    assert call_count(log_path) == 1
    assert field(result, "file") is None

    # Nothing written to verification/<component>/generated-test/
    gen_test_dir = repo_root / "verification" / "foo" / "generated-test"
    assert files_under(gen_test_dir) == []
    assert not (gen_test_dir / "test_ac_foo_003.py").exists()

    # Nothing written to the local cache.
    assert files_under(repo_root / ".hotdocs" / "cache") == []

    # A subsequent call with the same inputs must not be served from cache:
    # the model is called again and its (now conforming) reply is used.
    good_code = "def test_ok():\n    assert True"

    def good_reply(n):
        return (
            "-----BEGIN FILE " + n + "-----\n"
            + good_code
            + "\n-----END FILE " + n + "-----"
        )

    log_path2 = tmp_path / "calls2.log"
    backend2 = make_backend(log_path2, good_reply)
    result2 = test_author.author_test(
        make_bundle(), MODEL, 0, repo_root=repo_root, llm_backend=backend2
    )

    assert call_count(log_path2) == 1
    assert field(result2, "cache_hit") is False
    f2 = field(result2, "file")
    assert f2 is not None
    assert body(field(f2, "content")) == good_code