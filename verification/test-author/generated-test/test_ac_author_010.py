import re

import pytest

import test_author


class _Bundle(dict):
    """A CriterionBundle stand-in readable both as a mapping and by attribute."""

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)


def _field(value, name):
    return value.get(name) if isinstance(value, dict) else getattr(value, name, None)


_BAR_INTERFACE = (
    "# Library\n\n"
    "```\n"
    "bar(x: int) -> BarResult\n"
    "```\n\n"
    "# `BarResult`\n\n"
    "```json\n"
    "{\"value\": 4, \"ok\": true}\n"
    "```\n"
)


def _bundle_with_dependency():
    return _Bundle(
        component_id="comp-foo",
        criterion_id="AC-FOO-001",
        covers="R-FOO-001",
        criterion_text=(
            "Given x = 2\nWhen foo(x) is called\nThen it returns 4\n"
        ),
        requirement_text=(
            "# R-FOO-001\n\n**R-FOO-001** — `foo(x)` MUST return `2 * x`."
        ),
        interface="# Library\n\n```\nfoo(x: int) -> int\n```\n",
        glossary="# Glossary\n\n- **Foo** — a test term.\n",
        dependency_interfaces={"comp-bar-baz": _BAR_INTERFACE},
        module_names=["foo"],
    )


def _bundle_without_dependency():
    return _Bundle(
        component_id="comp-qux-thing",
        criterion_id="AC-QUX-THING-002",
        covers="R-QUX-THING-002",
        criterion_text=(
            "Given a value\nWhen qux(value) is called\nThen it echoes the value\n"
        ),
        requirement_text=(
            "# R-QUX-THING-002\n\n**R-QUX-THING-002** — `qux(v)` MUST return `v`."
        ),
        interface="# Library\n\n```\nqux(v: str) -> str\n```\n",
        glossary="# Glossary\n\n- **Qux** — another test term.\n",
        dependency_interfaces={},
    )


_NONCE_RE = re.compile(r"-----BEGIN FILE ([0-9a-fA-F]+)-----")

_TEST_FILE_BODY = "def test_placeholder():\n    assert True\n"


def _make_backend(prompts):
    def backend(prompt=None, model=None, *args, **params):
        if prompt is None:
            prompt = params.get("prompt", "")
        prompts.append(prompt)
        match = _NONCE_RE.search(prompt or "")
        nonce = match.group(1) if match else "0" * 32
        text = (
            f"-----BEGIN FILE {nonce}-----\n"
            f"{_TEST_FILE_BODY}"
            f"-----END FILE {nonce}-----\n"
        )
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    return backend


def _collapse(text):
    return re.sub(r"\s+", " ", text)


def _normalize(text):
    return _collapse(text.replace("`", "")).lower()


@pytest.fixture
def isolated_env(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.chdir(work)
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    return repo_root


def _capture_prompt(bundle, repo_root):
    prompts = []
    result = test_author.author_test(
        bundle,
        "claude-sonnet-5",
        seed=0,
        repo_root=repo_root,
        llm_backend=_make_backend(prompts),
    )
    assert prompts, "author_test never sent a prompt to the model backend"
    assert _field(result, "model_call_error") is None
    return prompts[0]


@pytest.mark.parametrize(
    "bundle_factory",
    [_bundle_with_dependency, _bundle_without_dependency],
    ids=["with-dependency", "without-dependency"],
)
def test_prompt_states_dependency_resolution_convention(isolated_env, bundle_factory):
    repo_root = isolated_env
    prompt = _capture_prompt(bundle_factory(), repo_root)
    raw = _collapse(prompt)
    norm = _normalize(prompt)

    # --- no DEPENDENCY is statically importable (never the component under test) ---
    occurrences = [m.start() for m in re.finditer(r"statically importable", norm)]
    assert occurrences, "prompt never states that dependencies are not statically importable"
    assert re.search(r"no dependenc[a-z]*[^.]{0,120}statically importable", norm), (
        "prompt does not state that no dependency is statically importable"
    )
    for pos in occurrences:
        window = norm[max(0, pos - 200):pos]
        assert "dependenc" in window, (
            "a 'statically importable' claim is not scoped to dependencies: "
            + norm[max(0, pos - 200):pos + 40]
        )
    assert not re.search(
        r"component under test (itself )?is (not|never) statically importable", norm
    ), "prompt claims the component under test itself is not statically importable"

    # --- component under test: plain import, no custom loader ---
    loader_positions = [m.start() for m in re.finditer(r"no custom loader", norm)]
    assert loader_positions, "prompt never says the component under test needs no custom loader"
    assert any(
        "component under test" in norm[max(0, p - 120):p]
        and "plain" in norm[p:p + 120]
        and "import" in norm[p:p + 120]
        for p in loader_positions
    ), "prompt does not say the component under test is imported via a plain import with no custom loader"

    # --- real resolution path for a dependency ---
    assert "<repo_root>/gen/<dependency-slug>/<module_name>.py" in raw, (
        "prompt does not name the flat <repo_root>/gen/<dependency-slug>/<module_name>.py path"
    )
    assert (
        "<module_name>/__init__.py" in raw or "<dependency-slug>/__init__.py" in raw
    ), "prompt does not name the package __init__.py resolution path"

    # --- fake dependency: flat-module file under a temporary repo_root ---
    assert re.search(r"flat[- ]module", norm), "prompt does not require flat-module shape"
    assert re.search(r"always[^.]{0,40}flat[- ]module", norm), (
        "prompt does not say the fake is ALWAYS in flat-module shape"
    )
    assert "temporary" in norm and "repo_root" in norm, (
        "prompt does not instruct writing the fake under a temporary repo_root"
    )
    assert "sys.modules" in norm, "prompt does not mention sys.modules injection"
    assert "mock.patch" in norm, "prompt does not rule out mock.patch by name"

    # --- module_name definition, never "__init__" ---
    assert "slug with hyphens replaced by underscores" in norm, (
        "prompt does not define module_name as the slug with hyphens replaced by underscores"
    )
    assert re.search(r"never[^.]{0,60}\"?__init__\"?", norm), (
        "prompt does not state module_name is never literally \"__init__\""
    )

    # --- literal snippet: sys.modules assignment before exec_module ---
    sys_line = "sys.modules[module_name] = module"
    exec_line = "spec.loader.exec_module(module)"
    assert sys_line in prompt, "prompt lacks the literal sys.modules[module_name] = module line"
    assert exec_line in prompt, "prompt lacks the literal spec.loader.exec_module(module) line"

    ordered_ok = False
    for m in re.finditer(re.escape(exec_line), prompt):
        preceding = prompt[:m.start()]
        cut = preceding.rfind("module_from_spec(")
        segment = preceding[cut:] if cut != -1 else preceding
        if sys_line in segment:
            ordered_ok = True
            break
    assert ordered_ok, (
        "prompt's snippet does not assign sys.modules[module_name] = module "
        "before calling spec.loader.exec_module(module)"
    )