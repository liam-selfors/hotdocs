# hotdocs-criterion: sha256:1b8105e8c965f11d90e8392e4abffd42ba55b854ced07c0b1e465286d0455637
import pytest

import test_author


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


class _Bundle(dict):
    """A CriterionBundle stand-in readable both as a mapping and by attribute."""

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)


def _make_bundle():
    return _Bundle(
        component_id="comp-foo",
        criterion_id="AC-FOO-001",
        covers="R-FOO-001",
        criterion_text=(
            "Given x = 2\n"
            "When foo(x) is called\n"
            "Then it returns 4"
        ),
        requirement_text="**R-FOO-001** — `foo(x)` MUST return `2 * x`.",
        interface="# Library\n\n```\nfoo(x: int) -> int\n```",
        glossary="# Glossary\n\n- **Foo** — a test term.",
        dependency_interfaces={},
        module_names=["foo"],
    )


def _raising_backend(calls):
    def backend(prompt, model, **params):
        calls.append(model)
        raise ConnectionError("simulated network failure: connection refused")

    return backend


def _error_response_backend(calls):
    def backend(prompt, model, **params):
        calls.append(model)
        return {
            "text": None,
            "model": model,
            "backend": "mock",
            "model_call_error": {
                "category": "network",
                "message": "simulated network failure",
            },
        }

    return backend


@pytest.mark.parametrize(
    "make_backend",
    [_raising_backend, _error_response_backend],
    ids=["backend-raises", "backend-returns-network-error"],
)
def test_network_error_reported_as_model_call_error(tmp_path, monkeypatch, make_backend):
    # Ensure the cache resolves to a fresh local store under tmp_path (no hit possible).
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    monkeypatch.chdir(tmp_path)

    calls = []
    backend = make_backend(calls)
    bundle = _make_bundle()

    result = test_author.author_test(
        bundle,
        "mock-model",
        0,
        repo_root=tmp_path,
        llm_backend=backend,
    )

    # The mock model was actually reached (a model call was attempted).
    assert len(calls) >= 1

    model_call_error = field(result, "model_call_error")
    assert model_call_error is not None
    assert model_call_error != {}
    assert model_call_error is not False

    assert field(result, "file") is None
    assert field(result, "cache_hit") is False

    # No test file was written for a failed authoring attempt.
    written = tmp_path / "verification" / "foo" / "generated-test" / "test_ac_foo_001.py"
    assert not written.exists()