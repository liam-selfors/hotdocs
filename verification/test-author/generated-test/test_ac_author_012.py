import re
from pathlib import Path

import pytest

import test_author


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


def _bundle_foo():
    return _Bundle(
        component_id="comp-foo",
        criterion_id="AC-FOO-001",
        covers="R-FOO-001",
        criterion_text=(
            "# AC-FOO-001\n\nCovers: R-FOO-001\nKind: generated-test\n\n"
            "```gherkin\nGiven x = 2\nWhen foo(x) is called\nThen it returns 4\n```\n"
        ),
        requirement_text="# R-FOO-001\n\n**R-FOO-001** — `foo(x)` MUST return `2 * x`.",
        interface="# Library\n\n```\nfoo(x: int) -> int\n```\n",
        glossary="# Glossary\n\n- **Foo** — a test term.\n",
        dependency_interfaces={},
        module_names=["foo"],
    )


def _bundle_bar():
    return _Bundle(
        component_id="comp-bar",
        criterion_id="AC-BAR-002",
        covers="R-BAR-002",
        criterion_text=(
            "# AC-BAR-002\n\nCovers: R-BAR-002\nKind: generated-test\n\n"
            "```gherkin\nGiven a value 3\nWhen bar(3) is called\nThen it returns 6\n```\n"
        ),
        requirement_text="# R-BAR-002\n\n**R-BAR-002** — `bar(x)` MUST return `foo(x)`.",
        interface="# Library\n\n```\nbar(x: int) -> int\n```\n",
        glossary="# Glossary\n\n- **Bar** — another test term.\n",
        dependency_interfaces={
            "comp-foo": "# Library\n\n```\nfoo(x: int) -> int\n```\n",
        },
        module_names=["bar"],
    )


def _make_backend(log_dir: Path):
    log_dir.mkdir(parents=True, exist_ok=True)

    def backend(prompt, model, **params):
        idx = len(list(log_dir.glob("prompt_*.txt")))
        (log_dir / f"prompt_{idx}.txt").write_text(prompt, encoding="utf-8")
        m = re.search(r"-----BEGIN FILE ([0-9a-fA-F]{32})-----", prompt)
        nonce = m.group(1) if m else "0" * 32
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


_REQUIRED_WORD = re.compile(r"\b(must|required|requires|always)\b", re.IGNORECASE)
_SYNTHETIC_WORD = re.compile(
    r"(synthetic|fixture|from scratch|construct)", re.IGNORECASE
)


def _window_states_required_frontmatter(window: str) -> bool:
    lower = window.lower()
    return (
        re.search(r"\bid\b", lower) is not None
        and "title" in lower
        and "status" in lower
        and "owners" in lower
        and "component.md" in lower
        and _REQUIRED_WORD.search(window) is not None
    )


def _windows_around(text: str, needle: str, radius: int = 900):
    for m in re.finditer(re.escape(needle), text, re.IGNORECASE):
        start = max(0, m.start() - radius)
        end = min(len(text), m.end() + radius)
        yield text[start:end]


@pytest.mark.parametrize("bundle_factory", [_bundle_foo, _bundle_bar])
def test_prompt_states_required_component_md_frontmatter(
    tmp_path, monkeypatch, bundle_factory
):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.chdir(work)

    log_dir = tmp_path / "prompt_log"
    backend = _make_backend(log_dir)

    bundle = bundle_factory()

    # Sanity: the bundle's own content must not already carry the statement,
    # so whatever we find comes from the prompt author_test builds itself.
    bundle_text = " ".join(
        str(v) for v in bundle.values() if isinstance(v, str)
    ).lower()
    assert "owners" not in bundle_text
    assert "component.md" not in bundle_text

    result = test_author.author_test(
        bundle, "claude-sonnet-5", 0, repo_root=repo_root, llm_backend=backend
    )
    assert result is not None
    assert _field(result, "model_call_error") is None

    prompts = sorted(log_dir.glob("prompt_*.txt"))
    assert prompts, "author_test never called the model backend with a prompt"

    for prompt_file in prompts:
        prompt = prompt_file.read_text(encoding="utf-8")

        # id, title, status and owners are stated as always required on a component.md
        stating_windows = [
            w for w in _windows_around(prompt, "owners")
            if _window_states_required_frontmatter(w)
        ]
        assert stating_windows, (
            "prompt does not state that id, title, status and owners are "
            "required on a component.md"
        )
        assert any(
            re.search(r"\balways\b", w, re.IGNORECASE) for w in stating_windows
        ), "prompt does not state these frontmatter fields are ALWAYS required"

        # ... and that a synthetic component.md the test constructs must include them
        assert any(
            _SYNTHETIC_WORD.search(w) for w in stating_windows
        ), (
            "prompt does not state that a synthetic component.md the test "
            "constructs must include id, title, status and owners"
        )