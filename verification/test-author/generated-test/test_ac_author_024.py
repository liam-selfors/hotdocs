import re

import pytest

import test_author


NONCE_RE = re.compile(r"-----BEGIN FILE ([0-9a-f]{32})-----")


class _Bundle(dict):
    """A CriterionBundle stand-in readable both as a mapping and by attribute."""

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc


def _field(value, name):
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


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
        requirement_text="# R-FOO-001\n\n**R-FOO-001** — `foo(x)` MUST return `2 * x`.\n",
        interface="# Library\n\n```\nfoo(x: int) -> int\n```\n",
        glossary="# Glossary\n\n- **Foo** — a test term.\n",
        dependency_interfaces={},
        module_names=["foo"],
    )


def _bundle_with_dependency():
    return _Bundle(
        component_id="comp-baz",
        criterion_id="AC-BAZ-007",
        covers="R-BAZ-007",
        criterion_text=(
            "Given a value v\n"
            "When baz(v) is called\n"
            "Then it delegates to comp-bar's bar(v) exactly once\n"
        ),
        requirement_text=(
            "# R-BAZ-007\n\n**R-BAZ-007** — `baz(v)` MUST call `bar(v)` "
            "exactly once and return its result.\n"
        ),
        interface="# Library\n\n```\nbaz(v: int) -> int\n```\n",
        glossary="# Glossary\n\n- **Baz** — another test term.\n",
        dependency_interfaces={
            "comp-bar": "# Library\n\n```\nbar(v: int) -> int\n```\n",
        },
    )


def _make_backend(captured):
    def backend(prompt=None, model=None, *args, **params):
        if prompt is None:
            prompt = params.get("prompt")
        captured.append(prompt)
        match = NONCE_RE.search(prompt or "")
        nonce = match.group(1) if match else "0" * 32
        text = (
            f"-----BEGIN FILE {nonce}-----\n"
            "def test_placeholder():\n"
            "    assert True\n"
            f"-----END FILE {nonce}-----\n"
        )
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    return backend


def _windows_around(text, needle, radius=1500):
    lowered = text.lower()
    start = 0
    while True:
        idx = lowered.find(needle, start)
        if idx < 0:
            return
        yield lowered[max(0, idx - radius): idx + len(needle) + radius]
        start = idx + 1


def _instructs_file_based_invocation_log(prompt):
    lowered = prompt.lower()
    if "sys.modules" not in lowered:
        return False
    for window in _windows_around(prompt, "sys.modules"):
        mentions_fake = "fake" in window
        mentions_file = "file" in window
        mentions_invocation = any(
            w in window
            for w in ("invocation", "invoked", "was used", " ran", "was called", "confirm")
        )
        mentions_record = any(w in window for w in ("append", "log", "record", "write"))
        mentions_test_path = any(
            w in window
            for w in (
                "test controls",
                "test-controlled",
                "your test",
                "the test",
                "temp",
                "tmp",
            )
        )
        mentions_negation = any(
            w in window for w in ("never", "not ", "don't", "must not", "do not")
        )
        mentions_in_process_list = any(
            w in window for w in ("in-process", "in process", "module-level", "module level", "list")
        )
        if all(
            (
                mentions_fake,
                mentions_file,
                mentions_invocation,
                mentions_record,
                mentions_test_path,
                mentions_negation,
                mentions_in_process_list,
            )
        ):
            return True
    return False


@pytest.mark.parametrize(
    "bundle_factory,seed",
    [(_bundle_plain, 11), (_bundle_with_dependency, 23)],
)
def test_prompt_instructs_file_based_fake_invocation_log(
    tmp_path, monkeypatch, bundle_factory, seed
):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    workdir = tmp_path / "work"
    workdir.mkdir()
    monkeypatch.chdir(workdir)

    captured = []
    backend = _make_backend(captured)

    result = test_author.author_test(
        bundle_factory(),
        "mock-model",
        seed,
        repo_root=repo_root,
        llm_backend=backend,
    )

    assert _field(result, "model_call_error") is None
    assert captured, "author_test never called the model backend, so no prompt was built"

    prompt = captured[0]
    assert isinstance(prompt, str) and prompt

    assert _instructs_file_based_invocation_log(prompt), (
        "prompt does not instruct confirming a fake's invocation via a "
        "test-controlled file (appended invocation record) rather than an "
        "in-process list read via sys.modules"
    )