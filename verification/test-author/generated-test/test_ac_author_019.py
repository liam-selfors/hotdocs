# hotdocs-criterion: sha256:64a73c2d3462f8544bc75dec7e83533961161335ef12f08399f71f829780157f
import re

import test_author


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


class Bundle(dict):
    """A CriterionBundle readable both as a mapping and by attribute."""

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)


def make_bundle():
    return Bundle(
        component_id="comp-foo",
        criterion_id="AC-FOO-001",
        covers="R-FOO-001",
        criterion_text=(
            "Given x = 2\n"
            "When foo(x) is called\n"
            "Then it returns 4\n"
        ),
        requirement_text="**R-FOO-001** — `foo(x)` MUST return `2 * x`.",
        interface="# Library\n\n```\nfoo(x: int) -> int\n```\n",
        glossary="# Glossary\n\n- **Foo** — a test term.\n",
        dependency_interfaces={},
        module_names=["foo"],
    )


NONCE_RE = re.compile(r"-----BEGIN FILE ([0-9a-f]{32})-----")


def test_backend_receives_only_prompt_and_model_no_seed(tmp_path):
    calls = []
    model = "claude-sonnet-5"

    def spy_backend(*args, **kwargs):
        calls.append((args, dict(kwargs)))
        if args:
            prompt = args[0]
        else:
            prompt = kwargs.get("prompt", "")
        m = NONCE_RE.search(prompt)
        nonce = m.group(1) if m else "0" * 32
        text = (
            "-----BEGIN FILE " + nonce + "-----\n"
            "import foo\n\n\ndef test_foo():\n    assert foo.foo(2) == 4\n"
            "-----END FILE " + nonce + "-----"
        )
        return {
            "text": text,
            "model": model,
            "backend": "spy",
            "model_call_error": None,
        }

    result = test_author.author_test(
        make_bundle(), model, 7, repo_root=tmp_path, llm_backend=spy_backend
    )

    assert calls, "the spy backend was never called"

    for args, kwargs in calls:
        # No seed keyword argument at all.
        assert "seed" not in kwargs, "seed was forwarded to the backend: " + repr(kwargs)

        # Only prompt and model are passed as positional arguments.
        assert len(args) == 2, "expected exactly (prompt, model) positionally, got " + repr(len(args))
        prompt, passed_model = args
        assert isinstance(prompt, str) and prompt
        assert passed_model == model

        # Nothing else (no bookkeeping params) is forwarded either.
        assert kwargs == {}, "unexpected extra keyword arguments: " + repr(sorted(kwargs))

    assert field(result, "model_call_error") is None