import urllib.error
from pathlib import Path

import pytest

import test_author


def _field(value, name):
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


class _Bundle(dict):
    """A CriterionBundle stand-in readable both as a mapping and by attribute,
    matching spec-bundle-assembler's documented dual-access dataclass shape."""

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc


def _make_bundle():
    criterion_text = (
        "Given x = 2\n"
        "When foo(x) is called\n"
        "Then it returns 4"
    )
    requirement_text = "# R-FOO-001\n\n**R-FOO-001** — `foo(x)` MUST return `2 * x`."
    interface = "# Library\n\n```\nfoo(x: int) -> int\n```"
    glossary = "# Glossary\n\n- **Foo** — a test term."
    return _Bundle(
        component_id="comp-foo",
        criterion_id="AC-FOO-001",
        covers="R-FOO-001",
        criterion_text=criterion_text,
        requirement_text=requirement_text,
        interface=interface,
        glossary=glossary,
        dependency_interfaces={},
        module_names=["foo"],
    )


def test_model_call_network_error_reported_as_model_call_error(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    workdir = tmp_path / "cwd"
    workdir.mkdir()
    monkeypatch.chdir(workdir)
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)

    invocation_log = tmp_path / "backend_invocations.log"

    def failing_backend(prompt, model, **params):
        with open(invocation_log, "a", encoding="utf-8") as fh:
            fh.write("called model=%s\n" % model)
        raise urllib.error.URLError("simulated network failure")

    bundle = _make_bundle()

    result = test_author.author_test(
        bundle,
        "anthropic:claude-sonnet-5",
        0,
        repo_root=repo_root,
        llm_backend=failing_backend,
    )

    assert result is not None

    # The mock backend was actually reached (a model call was attempted).
    assert invocation_log.is_file(), "mock llm backend was never invoked"
    lines = [ln for ln in invocation_log.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(lines) >= 1

    model_call_error = _field(result, "model_call_error")
    file_value = _field(result, "file")
    cache_hit = _field(result, "cache_hit")

    assert model_call_error is not None, "expected a non-null model_call_error"
    assert model_call_error != {} and model_call_error != "", (
        "model_call_error must carry a real error, not an empty value"
    )
    assert file_value is None, "expected a null file on model-call error"
    assert cache_hit is False, "cache_hit must be false on model-call error"

    component_id = _field(result, "component_id")
    criterion_id = _field(result, "criterion_id")
    if component_id is not None:
        assert component_id == "comp-foo"
    if criterion_id is not None:
        assert criterion_id == "AC-FOO-001"