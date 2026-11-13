import re

import pytest

import test_author


NONCE_RE = re.compile(r"-----BEGIN FILE ([0-9a-f]{32})-----")


class _Bundle(dict):
    """A CriterionBundle that reads both as a mapping and by attribute."""

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc


def _field(value, name):
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def _make_backend(captured):
    def backend(*args, **kwargs):
        prompt = args[0] if args else kwargs.get("prompt")
        model = args[1] if len(args) > 1 else kwargs.get("model")
        captured.append(prompt)
        match = NONCE_RE.search(prompt or "")
        nonce = match.group(1) if match else "0" * 32
        body = "def test_placeholder():\n    assert True\n"
        text = (
            "-----BEGIN FILE " + nonce + "-----\n"
            + body
            + "-----END FILE " + nonce + "-----\n"
        )
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    return backend


def _bundle_plain():
    return _Bundle(
        component_id="comp-foo",
        criterion_id="AC-FOO-001",
        covers="R-FOO-001",
        criterion_text="Given x = 2\nWhen foo(x) is called\nThen it returns 4",
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
        criterion_text="Given y = 3\nWhen baz(y) is called\nThen it returns 9",
        requirement_text="# R-BAZ-002\n\n**R-BAZ-002** — `baz(y)` MUST return `y * y`.",
        interface="# Library\n\n```\nbaz(y: int) -> int\n```",
        glossary="# Glossary\n\n- **Baz** — another test term.",
        dependency_interfaces={
            "comp-qux": "# Library\n\n```\nqux(z: int) -> int\n```",
        },
        module_names=["baz"],
    )


def _normalize(text):
    text = text.replace("`", "")
    return re.sub(r"\s+", " ", text).lower()


def _window_has_all(text, anchor, required, any_of_groups=(), radius=500):
    start = 0
    while True:
        i = text.find(anchor, start)
        if i < 0:
            return False
        seg = text[max(0, i - radius): i + len(anchor) + radius]
        if all(r in seg for r in required) and all(
            any(alt in seg for alt in group) for group in any_of_groups
        ):
            return True
        start = i + 1


def _capture_prompt(bundle, tmp_path, monkeypatch, subdir):
    repo_root = tmp_path / subdir
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    captured = []
    result = test_author.author_test(
        bundle,
        "claude-sonnet-5",
        0,
        repo_root=repo_root,
        llm_backend=_make_backend(captured),
    )
    assert captured, (
        "author_test never called the injected llm_backend; result: %r"
        % (result,)
    )
    prompt = captured[0]
    assert isinstance(prompt, str) and prompt
    err = _field(result, "model_call_error")
    assert err is None, "unexpected model_call_error: %r" % (err,)
    return prompt


@pytest.mark.parametrize(
    "bundle_factory", [_bundle_plain, _bundle_with_dependency]
)
def test_prompt_states_frontmatter_status_scope_and_coverage_rules(
    bundle_factory, tmp_path, monkeypatch
):
    bundle = bundle_factory()
    # Sanity: the bundle itself carries none of the asserted phrases, so any
    # hit must come from the prompt's own instructions.
    bundle_text = _normalize(
        " ".join(
            str(v) if not isinstance(v, dict) else " ".join(map(str, v.values()))
            for v in bundle.values()
        )
    )
    for phrase in (
        "draft", "ratified", "deprecated", "var-", "component.md",
        "decisions", "d<n>", "requirements/", "acceptance/", "covers:",
    ):
        assert phrase not in bundle_text

    prompt = _capture_prompt(bundle, tmp_path, monkeypatch, bundle_factory.__name__)
    text = _normalize(prompt)

    # 1. status must be exactly one of draft / ratified / deprecated.
    assert _window_has_all(
        text,
        "status",
        ["draft", "ratified", "deprecated"],
        any_of_groups=[("exactly", "one of")],
        radius=300,
    ), "prompt does not state status must be exactly one of draft/ratified/deprecated"

    # 2. Required frontmatter applies to VAR-*.md and D<N>.md as well as component.md.
    assert "component.md" in text
    assert "var-" in text
    assert ("d<n>" in text) or ("decisions/" in text)
    assert _window_has_all(
        text,
        "var-",
        ["component.md"],
        any_of_groups=[("d<n>", "decisions/")],
        radius=600,
    ), "prompt does not apply required frontmatter to VAR-*.md and D<N>.md alongside component.md"
    for field in ("id", "title", "status", "owners"):
        assert field in text

    # 3. Every requirements/ file needs a matching acceptance/ file covering it,
    #    for every component the fixture constructs.
    assert _window_has_all(
        text,
        "requirements/",
        ["acceptance/", "covers", "every", "component"],
        radius=500,
    ), "prompt does not state every requirements/ file needs a covering acceptance/ file for every fixture component"