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
            "Then it returns 4\n"
        ),
        requirement_text="**R-FOO-001** \u2014 `foo(x)` MUST return `2 * x`.",
        interface="# Library\n\n```\nfoo(x: int) -> int\n```\n",
        glossary="# Glossary\n\n- **Foo** \u2014 a test term.\n",
        dependency_interfaces={},
        module_names=["foo"],
    )


def _raising_backend(prompt, model, **params):
    raise ConnectionError("network unreachable")


def _error_response_backend(prompt, model, **params):
    return {
        "text": None,
        "model": model,
        "backend": "mock",
        "model_call_error": {"category": "network", "message": "network unreachable"},
    }


@pytest.mark.parametrize(
    "backend",
    [_raising_backend, _error_response_backend],
    ids=["backend-raises", "backend-reports-network-error"],
)
def test_ac_author_007_network_error_is_model_call_error(tmp_path, monkeypatch, backend):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    result = test_author.author_test(
        _make_bundle(),
        "mock:network-failure-model",
        seed=7,
        repo_root=repo_root,
        llm_backend=backend,
    )

    assert field(result, "model_call_error") is not None
    assert field(result, "file") is None
    assert field(result, "cache_hit") is False