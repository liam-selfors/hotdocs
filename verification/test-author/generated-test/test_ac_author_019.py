# hotdocs-criterion: sha256:64a73c2d3462f8544bc75dec7e83533961161335ef12f08399f71f829780157f
import dataclasses
import re

import test_author


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


@dataclasses.dataclass
class FakeCriterionBundle:
    component_id: str
    criterion_id: str
    covers: str
    criterion_text: str
    requirement_text: str
    interface: str
    glossary: str
    dependency_interfaces: dict = dataclasses.field(default_factory=dict)
    module_names: list = dataclasses.field(default_factory=list)

    def __getitem__(self, key):
        try:
            return getattr(self, key)
        except AttributeError:
            raise KeyError(key)

    def get(self, key, default=None):
        return getattr(self, key, default)

    def keys(self):
        return [f.name for f in dataclasses.fields(self)]

    def __iter__(self):
        return iter(self.keys())

    def __contains__(self, key):
        return key in self.keys()

    def __len__(self):
        return len(self.keys())


def make_bundle():
    return FakeCriterionBundle(
        component_id="comp-foo",
        criterion_id="AC-FOO-001",
        covers="R-FOO-001",
        criterion_text=(
            "# AC-FOO-001\n\nCovers: R-FOO-001\nKind: generated-test\n\n"
            "```gherkin\nGiven x = 2\nWhen foo(x) is called\nThen it returns 4\n```\n"
        ),
        requirement_text="# R-FOO-001\n\n**R-FOO-001** \u2014 `foo(x)` MUST return `2 * x`.\n",
        interface="# Library\n\n```\nfoo(x: int) -> int\n```\n",
        glossary="# Glossary\n\n- **Foo** \u2014 a test term.\n",
        dependency_interfaces={},
        module_names=["foo"],
    )


NONCE_RE = re.compile(r"-----BEGIN FILE ([0-9a-fA-F]+)-----")


def test_backend_called_with_only_prompt_and_model_no_seed(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)

    calls = []

    def spy_backend(*args, **kwargs):
        calls.append((args, dict(kwargs)))
        prompt = args[0] if args else kwargs.get("prompt", "")
        model_arg = args[1] if len(args) > 1 else kwargs.get("model")
        match = NONCE_RE.search(prompt or "")
        nonce = match.group(1) if match else "0" * 32
        text = (
            "-----BEGIN FILE " + nonce + "-----\n"
            "def test_x():\n    assert True\n"
            "-----END FILE " + nonce + "-----"
        )
        return {
            "text": text,
            "model": model_arg,
            "backend": "spy",
            "model_call_error": None,
        }

    model = "claude-sonnet-5"
    test_author.author_test(
        make_bundle(), model, 7, repo_root=tmp_path, llm_backend=spy_backend
    )

    assert calls, "spy backend was never called"
    for args, kwargs in calls:
        assert len(args) == 2, "expected exactly prompt and model positionally, got " + repr(args)
        assert isinstance(args[0], str)
        assert args[1] == model
        assert "seed" not in kwargs, "seed was forwarded to backend: " + repr(kwargs)