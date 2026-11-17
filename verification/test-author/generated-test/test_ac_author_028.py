import hashlib
import re
from pathlib import Path

import pytest

import test_author


CRITERION_TEXT = "Given a\nWhen b\nThen c"
REQUIREMENT_TEXT = "R-X-1 MUST c"
EXPECTED_HEX = hashlib.sha256(
    (CRITERION_TEXT + "\n" + REQUIREMENT_TEXT).encode("utf-8")
).hexdigest()
EXPECTED_HEADER = "# hotdocs-criterion: sha256:" + EXPECTED_HEX

NONCE_RE = re.compile(r"-----BEGIN FILE ([0-9a-f]{32})-----")


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
        covers="R-X-1",
        criterion_text=CRITERION_TEXT,
        requirement_text=REQUIREMENT_TEXT,
        interface="# Library\n\n```\nfoo(x: int) -> int\n```",
        glossary="# Glossary\n\n- **Foo** \u2014 a test term.",
        dependency_interfaces={},
        module_names=["foo"],
    )


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def make_backend(content, log_path):
    def backend(prompt, model, **params):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write("call\n")
        m = NONCE_RE.search(prompt)
        assert m is not None, "nonce not found in prompt"
        n = m.group(1)
        text = "-----BEGIN FILE " + n + "-----\n" + content + "\n-----END FILE " + n + "-----"
        return {"text": text, "model": model, "backend": "mock", "model_call_error": None}

    return backend


def make_forbidden_backend(log_path):
    def backend(prompt, model, **params):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write("forbidden call\n")
        raise AssertionError("model must never be called on a cache hit")

    return backend


def read_log(log_path):
    p = Path(log_path)
    return p.read_text(encoding="utf-8").splitlines() if p.exists() else []


@pytest.fixture(autouse=True)
def _local_cache(monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)


def test_header_on_miss_written_and_returned(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log = tmp_path / "log1.txt"

    result = test_author.author_test(
        make_bundle(), "mock", repo_root=repo_root,
        llm_backend=make_backend("import x", log),
    )

    assert field(result, "model_call_error") is None
    assert len(read_log(log)) == 1
    f = field(result, "file")
    content = field(f, "content")
    path = field(f, "path")

    expected = EXPECTED_HEADER + "\n" + "import x"
    assert content == expected
    written = (repo_root / path).read_text(encoding="utf-8")
    assert written == expected


def test_model_supplied_header_is_replaced_not_repeated(tmp_path):
    repo_root = tmp_path / "repo2"
    repo_root.mkdir()
    log = tmp_path / "log2.txt"

    result = test_author.author_test(
        make_bundle(), "mock", repo_root=repo_root,
        llm_backend=make_backend("# hotdocs-criterion: sha256:0000\nimport x", log),
    )

    assert field(result, "model_call_error") is None
    content = field(field(result, "file"), "content")
    lines = content.split("\n")
    header_lines = [i for i, line in enumerate(lines) if line.startswith("# hotdocs-criterion:")]
    assert header_lines == [0]
    assert lines[0] == EXPECTED_HEADER
    assert "sha256:0000\n" not in content


def test_header_on_cache_hit(tmp_path):
    repo_root = tmp_path / "repo3"
    repo_root.mkdir()
    log1 = tmp_path / "log3a.txt"
    log2 = tmp_path / "log3b.txt"

    first = test_author.author_test(
        make_bundle(), "mock", repo_root=repo_root,
        llm_backend=make_backend("import x", log1),
    )
    assert field(first, "model_call_error") is None

    second = test_author.author_test(
        make_bundle(), "mock", repo_root=repo_root,
        llm_backend=make_forbidden_backend(log2),
    )

    assert read_log(log2) == []
    assert field(second, "cache_hit") is True
    content = field(field(second, "file"), "content")
    assert content.split("\n", 1)[0] == EXPECTED_HEADER
    assert content.startswith(EXPECTED_HEADER + "\n")