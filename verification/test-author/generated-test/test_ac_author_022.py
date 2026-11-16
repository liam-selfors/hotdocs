import re

import pytest

import test_author


class _Bundle:
    """A CriterionBundle stand-in readable both as attributes and as a mapping."""

    _FIELDS = (
        "component_id",
        "criterion_id",
        "covers",
        "criterion_text",
        "requirement_text",
        "interface",
        "glossary",
        "dependency_interfaces",
    )

    def __init__(self, **kwargs):
        self._data = {}
        for name in self._FIELDS:
            value = kwargs.get(name)
            if name == "dependency_interfaces" and value is None:
                value = {}
            self._data[name] = value
            setattr(self, name, value)

    def __getitem__(self, key):
        return self._data[key]

    def get(self, key, default=None):
        return self._data.get(key, default)

    def __contains__(self, key):
        return key in self._data

    def keys(self):
        return self._data.keys()

    def items(self):
        return self._data.items()

    def values(self):
        return self._data.values()

    def __iter__(self):
        return iter(self._data)

    def __len__(self):
        return len(self._data)


def _bundle_plain():
    return _Bundle(
        component_id="comp-foo",
        criterion_id="AC-FOO-001",
        covers="R-FOO-001",
        criterion_text=(
            "Given x = 2\n"
            "When foo(x) is called\n"
            "Then it returns 4\n"
        ),
        requirement_text="# R-FOO-001\n\n**R-FOO-001** — `foo(x)` MUST return `2 * x`.",
        interface="# Library\n\n```\nfoo(x: int) -> int\n```",
        glossary="# Glossary\n\n- **Foo** — a test term.",
        dependency_interfaces={},
    )


def _bundle_with_dependency():
    return _Bundle(
        component_id="comp-baz",
        criterion_id="AC-BAZ-002",
        covers="R-BAZ-002",
        criterion_text=(
            "Given a value v = 3\n"
            "When baz(v) is called\n"
            "Then it returns bar(v) + 1\n"
        ),
        requirement_text="# R-BAZ-002\n\n**R-BAZ-002** — `baz(v)` MUST return `bar(v) + 1`.",
        interface="# Library\n\n```\nbaz(v: int) -> int\n```",
        glossary="# Glossary\n\n- **Baz** — another test term.",
        dependency_interfaces={
            "comp-bar": "# Library\n\n```\nbar(v: int) -> int\n```",
        },
    )


def _field(value, name):
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


_TEST_BODY = "def test_placeholder():\n    assert True\n"


def _make_backend(captured):
    def backend(prompt, model, **params):
        captured.append(prompt)
        match = re.search(r"-----BEGIN FILE ([0-9a-fA-F]{32})-----", prompt)
        nonce = match.group(1) if match else "0" * 32
        text = (
            f"-----BEGIN FILE {nonce}-----\n"
            f"{_TEST_BODY}"
            f"-----END FILE {nonce}-----\n"
        )
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    return backend


_NEGATION = re.compile(r"\bnever\b|\bmust not\b|\bdo not\b|\bdon't\b|\bnot\b|\bavoid\b|\bno\b")


def _windows_around(text, needle, before=700, after=900):
    lowered = text.lower()
    needle = needle.lower()
    windows = []
    start = 0
    while True:
        idx = lowered.find(needle, start)
        if idx < 0:
            break
        windows.append(lowered[max(0, idx - before): idx + len(needle) + after])
        start = idx + len(needle)
    return windows


@pytest.mark.parametrize("make_bundle", [_bundle_plain, _bundle_with_dependency])
def test_prompt_forbids_guessed_sys_modules_assertion_and_requires_file_record(
    tmp_path, monkeypatch, make_bundle
):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    monkeypatch.chdir(tmp_path)

    bundle = make_bundle()
    captured = []
    result = test_author.author_test(
        bundle,
        "mock-model",
        seed=0,
        repo_root=tmp_path,
        llm_backend=_make_backend(captured),
    )

    assert captured, "author_test never invoked the injected llm_backend with a prompt"
    prompt = captured[0]
    assert isinstance(prompt, str) and prompt

    # Sanity: the fixture bundle itself never mentions sys.modules, so any
    # mention in the prompt must come from author_test's own instructions.
    for name in _Bundle._FIELDS:
        value = bundle.get(name)
        assert "sys.modules" not in str(value)

    assert "sys.modules" in prompt, "prompt never mentions sys.modules"

    windows = _windows_around(prompt, "sys.modules")
    assert windows

    def _forbids_guess(window):
        return bool(_NEGATION.search(window)) and ("guess" in window)

    assert any(_forbids_guess(w) for w in windows), (
        "prompt does not instruct never to assert a fake was used via "
        "sys.modules under a guessed key"
    )

    def _requires_self_record(window):
        has_record = re.search(r"record|append|log\b|log ", window) is not None
        has_invocation = re.search(r"invocation|invoked|ran\b|was called|was used|called", window) is not None
        has_file = "file" in window
        return has_record and has_invocation and has_file

    assert any(_requires_self_record(w) for w in windows), (
        "prompt does not instruct the fake to record its own invocation "
        "(to a file) for the test to assert against"
    )

    error = _field(result, "model_call_error")
    assert error is None