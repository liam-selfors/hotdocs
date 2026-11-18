# hotdocs-criterion: sha256:72f8dbe0e9cee3ed73f6db59e0a35aac433848d1e63055b0431eb93e7d4a09b4
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


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


class Bundle:
    """A CriterionBundle stand-in readable both by attribute and as a mapping."""

    _FIELDS = (
        "component_id",
        "criterion_id",
        "covers",
        "criterion_text",
        "requirement_text",
        "interface",
        "glossary",
        "dependency_interfaces",
        "module_names",
    )

    def __init__(self, **kwargs):
        for name in self._FIELDS:
            setattr(self, name, kwargs.get(name))

    def __getitem__(self, key):
        if key not in self._FIELDS:
            raise KeyError(key)
        return getattr(self, key)

    def get(self, key, default=None):
        if key in self._FIELDS:
            return getattr(self, key)
        return default

    def __contains__(self, key):
        return key in self._FIELDS

    def keys(self):
        return list(self._FIELDS)

    def __iter__(self):
        return iter(self._FIELDS)

    def __len__(self):
        return len(self._FIELDS)

    def items(self):
        return [(k, getattr(self, k)) for k in self._FIELDS]

    def values(self):
        return [getattr(self, k) for k in self._FIELDS]


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


NONCE_RE = re.compile(r"-----BEGIN FILE ([0-9a-f]{32})-----")


def make_backend(content, log_path):
    def backend(prompt, model, **params):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write("called\n")
        m = NONCE_RE.search(prompt)
        assert m is not None, "prompt carries no BEGIN FILE nonce marker"
        n = m.group(1)
        text = (
            "-----BEGIN FILE " + n + "-----\n"
            + content
            + "\n-----END FILE " + n + "-----"
        )
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    return backend


def make_never_backend(log_path):
    def backend(prompt, model, **params):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write("called\n")
        return {
            "text": None,
            "model": model,
            "backend": "mock",
            "model_call_error": {"category": "network", "message": "must not be called"},
        }

    return backend


def body(content):
    first, _, rest = content.partition("\n")
    return rest if first.startswith("# hotdocs-criterion:") else content


@pytest.fixture(autouse=True)
def _isolate(monkeypatch, tmp_path):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    monkeypatch.chdir(tmp_path)


def _file_of(result):
    f = field(result, "file")
    assert f is not None
    return field(f, "path"), field(f, "content")


def test_header_prepended_on_miss_and_written(tmp_path):
    repo_root = tmp_path / "repo1"
    repo_root.mkdir()
    log = tmp_path / "log1.txt"

    result = test_author.author_test(
        make_bundle(), "mock", repo_root=repo_root,
        llm_backend=make_backend("import x", log),
    )

    assert field(result, "model_call_error") is None
    path, content = _file_of(result)
    expected = EXPECTED_HEADER + "\n" + "import x"
    assert content == expected

    written = Path(repo_root) / path
    assert written.is_file()
    assert written.read_text(encoding="utf-8") == expected


def test_model_supplied_header_is_replaced_not_repeated(tmp_path):
    repo_root = tmp_path / "repo2"
    repo_root.mkdir()
    log = tmp_path / "log2.txt"

    result = test_author.author_test(
        make_bundle(), "mock", repo_root=repo_root,
        llm_backend=make_backend("# hotdocs-criterion: sha256:0000\nimport x", log),
    )

    assert field(result, "model_call_error") is None
    path, content = _file_of(result)
    lines = content.splitlines()
    header_lines = [ln for ln in lines if ln.startswith("# hotdocs-criterion:")]
    assert len(header_lines) == 1
    assert lines[0] == EXPECTED_HEADER
    assert "sha256:0000\n" not in content + "\n" or lines[0] != "# hotdocs-criterion: sha256:0000"
    assert body(content) == "import x"

    written = (Path(repo_root) / path).read_text(encoding="utf-8")
    assert written == content


def test_cache_hit_carries_same_header(tmp_path):
    repo_root = tmp_path / "repo3"
    repo_root.mkdir()
    log1 = tmp_path / "log3a.txt"
    log2 = tmp_path / "log3b.txt"

    first = test_author.author_test(
        make_bundle(), "mock", repo_root=repo_root,
        llm_backend=make_backend("import x", log1),
    )
    assert field(first, "model_call_error") is None
    _, first_content = _file_of(first)
    assert first_content.splitlines()[0] == EXPECTED_HEADER

    second = test_author.author_test(
        make_bundle(), "mock", repo_root=repo_root,
        llm_backend=make_never_backend(log2),
    )

    assert not log2.exists() or log2.read_text(encoding="utf-8") == ""
    assert field(second, "cache_hit") is True
    path, content = _file_of(second)
    assert content.splitlines()[0] == EXPECTED_HEADER
    assert content.startswith(EXPECTED_HEADER + "\n")
    assert body(content) == "import x"

    written = (Path(repo_root) / path).read_text(encoding="utf-8")
    assert written.startswith(EXPECTED_HEADER + "\n")