"""AC-AUTHOR-009: author_test extracts strictly from between the
nonce-delimited BEGIN/END FILE markers, and a response with no marker
pair is a distinct authoring failure that writes nothing to cache or disk.
"""

import dataclasses
import os
import re
from pathlib import Path

import pytest

import test_author


GLOSSARY = "# Glossary\n\n- **Foo** \u2014 a test term.\n"

CRITERION_TEXT = (
    "# AC-FOO-001\n\n"
    "Covers: R-FOO-001\n"
    "Kind: generated-test\n\n"
    "Given x = 2\n"
    "When foo(x) is called\n"
    "Then it returns 4\n"
)

REQUIREMENT_TEXT = "# R-FOO-001\n\n**R-FOO-001** \u2014 `foo(x)` MUST return `2 * x`.\n"

INTERFACE_TEXT = "# Library\n\n    foo(x: int) -> int\n"

REAL_TEST_CODE = (
    "import foo\n"
    "\n"
    "\n"
    "def test_ac_foo_001_doubles_two_marker_payload_7f3a():\n"
    "    assert foo.foo(2) == 4\n"
)

NARRATION_BEFORE = "Sure! Here is the requested test file for AC-FOO-001, enjoy."
NARRATION_AFTER = "Let me know if you would like any further changes to it."


@dataclasses.dataclass
class FakeCriterionBundle:
    """Mirrors spec-bundle-assembler's CriterionBundle: a dataclass with the
    documented fields, in order, that also reads as a mapping."""

    component_id: str
    criterion_id: str
    covers: str
    criterion_text: str
    requirement_text: str
    interface: str
    glossary: str
    dependency_interfaces: dict = dataclasses.field(default_factory=dict)
    module_names: list = dataclasses.field(default_factory=lambda: ["foo"])

    def _names(self):
        return [f.name for f in dataclasses.fields(self)]

    def __getitem__(self, key):
        if key in self._names():
            return getattr(self, key)
        raise KeyError(key)

    def get(self, key, default=None):
        if key in self._names():
            return getattr(self, key)
        return default

    def __contains__(self, key):
        return key in self._names()

    def keys(self):
        return list(self._names())

    def values(self):
        return [getattr(self, n) for n in self._names()]

    def items(self):
        return [(n, getattr(self, n)) for n in self._names()]

    def __iter__(self):
        return iter(self._names())

    def __len__(self):
        return len(self._names())


def _make_bundle():
    return FakeCriterionBundle(
        component_id="comp-foo",
        criterion_id="AC-FOO-001",
        covers="R-FOO-001",
        criterion_text=CRITERION_TEXT,
        requirement_text=REQUIREMENT_TEXT,
        interface=INTERFACE_TEXT,
        glossary=GLOSSARY,
        dependency_interfaces={},
    )


def _field(value, name):
    if value is None:
        return None
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def _extract_nonce(prompt):
    candidates = re.findall(r"-----BEGIN FILE ([0-9A-Za-z]+)-----", prompt)
    assert candidates, "prompt carries no '-----BEGIN FILE <nonce>-----' instruction"
    hex32 = [c for c in candidates if re.fullmatch(r"[0-9a-fA-F]{32}", c)]
    return hex32[0] if hex32 else candidates[0]


def _model_response(text, model):
    return {
        "text": text,
        "model": model,
        "backend": "mock",
        "model_call_error": None,
    }


def _wrapped_backend(calls):
    def backend(prompt, model, **params):
        calls.append(prompt)
        nonce = _extract_nonce(prompt)
        text = (
            NARRATION_BEFORE + "\n"
            "```python\n"
            "-----BEGIN FILE " + nonce + "-----\n"
            + REAL_TEST_CODE
            + "-----END FILE " + nonce + "-----\n"
            "```\n"
            + NARRATION_AFTER + "\n"
        )
        return _model_response(text, model)

    return backend


def _markerless_backend(calls):
    def backend(prompt, model, **params):
        calls.append(prompt)
        text = (
            "Sure, here is a test file:\n"
            "```python\n"
            + REAL_TEST_CODE
            + "```\n"
            "Hope this helps.\n"
        )
        return _model_response(text, model)

    return backend


def _files_under(path):
    path = Path(path)
    if not path.exists():
        return []
    return [p for p in path.rglob("*") if p.is_file()]


@pytest.fixture
def repo_root(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    root.mkdir()
    monkeypatch.chdir(root)
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    return root


def test_extracts_exactly_between_markers_discarding_fence_and_narration(repo_root):
    calls = []
    result = test_author.author_test(
        _make_bundle(),
        "mock-model",
        0,
        repo_root=repo_root,
        llm_backend=_wrapped_backend(calls),
    )

    assert len(calls) == 1, "the mock backend should have been called exactly once"
    nonce = _extract_nonce(calls[0])

    assert _field(result, "model_call_error") is None
    file_ = _field(result, "file")
    assert file_ is not None, "a well-formed marker pair must produce a file"
    content = _field(file_, "content")
    assert isinstance(content, str)

    # Exactly the text between the markers (modulo the line breaks that
    # directly abut the marker lines themselves).
    assert content.strip("\r\n") == REAL_TEST_CODE.strip("\r\n")
    assert REAL_TEST_CODE.strip("\r\n") in content

    # Nothing from outside or of the markers themselves leaks in.
    assert "```" not in content
    assert NARRATION_BEFORE not in content
    assert NARRATION_AFTER not in content
    assert "-----BEGIN FILE" not in content
    assert "-----END FILE" not in content
    assert nonce not in content


def test_no_marker_pair_is_distinct_failure_writing_nothing(repo_root):
    calls = []
    result = test_author.author_test(
        _make_bundle(),
        "mock-model",
        0,
        repo_root=repo_root,
        llm_backend=_markerless_backend(calls),
    )

    assert len(calls) == 1, "the mock backend should have been called exactly once"
    assert _field(result, "file") is None
    assert not _field(result, "cache_hit")

    # Nothing written to verification/<component>/generated-test/.
    assert _files_under(repo_root / "verification") == []
    assert not (repo_root / "verification" / "foo" / "generated-test").exists() or \
        _files_under(repo_root / "verification" / "foo" / "generated-test") == []
    # Nothing written to the local cache store.
    assert _files_under(repo_root / ".hotdocs" / "cache") == []

    # And the failure was not cached: a subsequent identical call with a
    # conforming response must be a real miss that calls the model again.
    calls2 = []
    result2 = test_author.author_test(
        _make_bundle(),
        "mock-model",
        0,
        repo_root=repo_root,
        llm_backend=_wrapped_backend(calls2),
    )
    assert len(calls2) == 1, "the failed attempt must not have been cached"
    assert not _field(result2, "cache_hit")
    file2 = _field(result2, "file")
    assert file2 is not None
    assert _field(file2, "content").strip("\r\n") == REAL_TEST_CODE.strip("\r\n")