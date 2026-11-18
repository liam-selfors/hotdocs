# hotdocs-criterion: sha256:9461041486b91ab9a0d85d1990794a3348688bd2810709141b243d486bf291fb
import json
import re

import generator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


class _Bundle(dict):
    """A SpecBundle stand-in readable both as a mapping and by attribute."""

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)


def _make_bundle():
    return _Bundle(
        component_id="comp-foo",
        spec_bundle_hash="sha256:" + "a" * 64,
        spec="# Foo\n\n## Purpose\n\nFoo doubles a number.\n\n# R-FOO-001\n\n**R-FOO-001** \u2014 `foo(x)` MUST return `2 * x`.",
        interface="# Library\n\n```\nfoo(x: int) -> int\n```",
        constraints="# Constraints\n\nNone.",
        dependency_interfaces={},
        dependency_context={},
        dependency_usage={},
        vars={},
        glossary="# Glossary\n\n- **Foo** \u2014 a test term.",
        hint_code=None,
    )


def _make_backend(log_path):
    def backend(prompt, model, **params):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"model": model}) + "\n")
        nonce = re.search(r"-----BEGIN FILE ([0-9a-f]{32}):", prompt).group(1)
        text = (
            "-----BEGIN FILE " + nonce + ": foo.py-----\n"
            "def foo(x):\n"
            "    return 2 * x\n"
            "-----END FILE " + nonce + "-----\n"
            "-----END REPLY " + nonce + "-----\n"
        )
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    return backend


def test_model_identifier_passed_through_unchanged(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "mock_calls.log"

    bundle = _make_bundle()
    backend = _make_backend(log_path)

    model_a = "test-model-alpha-1"
    model_b = "test-model-beta-2"

    result_a = generator.generate(bundle, model_a, repo_root=repo_root, llm_backend=backend)
    result_b = generator.generate(bundle, model_b, repo_root=repo_root, llm_backend=backend)

    assert log_path.is_file(), "mock model was never called"
    calls = [
        json.loads(line)
        for line in log_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(calls) == 2, calls
    assert calls[0]["model"] == model_a
    assert calls[1]["model"] == model_b

    for result, model in ((result_a, model_a), (result_b, model_b)):
        assert field(result, "model_call_error") is None
        assert field(result, "refused") is None
        assert field(result, "cache_hit") is False
        assert field(result, "model") == model
        assert field(result, "files")