# hotdocs-criterion: sha256:72f8dbe0e9cee3ed73f6db59e0a35aac433848d1e63055b0431eb93e7d4a09b4
import hashlib
import re
from pathlib import Path

import pytest

import test_author


CRITERION_TEXT = "Given a\nWhen b\nThen c"
REQUIREMENT_TEXT = "R-X-1 MUST c"
HEADER_PREFIX = "# hotdocs-criterion:"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


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
        covers="R-X-1",
        criterion_text=CRITERION_TEXT,
        requirement_text=REQUIREMENT_TEXT,
        interface="# Library\n\n```\nfoo(x: int) -> int\n```",
        glossary="# Glossary\n\n- **Foo** - a test term.",
        dependency_interfaces={},
        module_names=["foo"],
    )


def expected_header():
    data = (CRITERION_TEXT + "\n" + REQUIREMENT_TEXT).encode("utf-8")
    return "# hotdocs-criterion: sha256:" + hashlib.sha256(data).hexdigest()


NONCE_RE = re.compile(r"-----BEGIN FILE ([0-9a-f]{32})-----")


def make_backend(content, log_path):
    def backend(prompt, model, **params):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write("call\n")
        m = NONCE_RE.search(prompt)
        assert m is not None, "prompt carries no BEGIN FILE nonce"
        n = m.group(1)
        text = "-----BEGIN FILE " + n + "-----\n" + content + "\n-----END FILE " + n + "-----"
        return {"text": text, "model": model, "backend": "mock", "model_call_error": None}

    return backend


def never_backend(log_path):
    def backend(prompt, model, **params):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write("call\n")
        raise AssertionError("model must never be called on a cache hit")

    return backend


def calls(log_path):
    p = Path(log_path)
    if not p.exists():
        return 0
    return len([line for line in p.read_text(encoding="utf-8").splitlines() if line])


@pytest.fixture(autouse=True)
def _local_cache(monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)


def run(repo_root, backend):
    return test_author.author_test(
        make_bundle(), "mock", repo_root=repo_root, llm_backend=backend
    )


def file_content_and_written(result, repo_root):
    assert field(result, "model_call_error") is None
    f = field(result, "file")
    content = field(f, "content")
    path = field(f, "path")
    written = (Path(repo_root) / path).read_text(encoding="utf-8")
    return content, written


def test_header_prepended_and_written(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log = tmp_path / "calls.log"
    result = run(repo_root, make_backend("import x", log))
    assert calls(log) >= 1
    content, written = file_content_and_written(result, repo_root)
    expected = expected_header() + "\n" + "import x"
    assert content == expected
    assert written == expected


def test_model_header_replaced_not_repeated(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log = tmp_path / "calls.log"
    result = run(repo_root, make_backend("# hotdocs-criterion: sha256:0000\nimport x", log))
    assert calls(log) >= 1
    content, written = file_content_and_written(result, repo_root)
    lines = content.splitlines()
    header_lines = [line for line in lines if line.startswith(HEADER_PREFIX)]
    assert len(header_lines) == 1
    assert lines[0] == expected_header()
    assert written.splitlines()[0] == expected_header()
    assert len([l for l in written.splitlines() if l.startswith(HEADER_PREFIX)]) == 1


def test_cache_hit_keeps_header(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log1 = tmp_path / "calls1.log"
    first = run(repo_root, make_backend("import x", log1))
    assert calls(log1) >= 1
    first_content, _ = file_content_and_written(first, repo_root)
    assert first_content.splitlines()[0] == expected_header()

    log2 = tmp_path / "calls2.log"
    second = run(repo_root, never_backend(log2))
    assert calls(log2) == 0
    assert field(second, "cache_hit") is True
    content = field(field(second, "file"), "content")
    assert content.startswith(expected_header() + "\n")
    assert content.splitlines()[0] == expected_header()