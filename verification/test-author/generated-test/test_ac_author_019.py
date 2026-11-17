import dataclasses
import re

import test_author


@dataclasses.dataclass
class _Bundle:
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

    def __contains__(self, key):
        return key in self.keys()

    def __iter__(self):
        return iter(self.keys())

    def __len__(self):
        return len(self.keys())


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _make_bundle():
    return _Bundle(
        component_id="comp-foo",
        criterion_id="AC-FOO-001",
        covers="R-FOO-001",
        criterion_text="Given x = 2\nWhen foo(x) is called\nThen it returns 4",
        requirement_text="**R-FOO-001** \u2014 `foo(x)` MUST return `2 * x`.",
        interface="# Library\n\n```\nfoo(x: int) -> int\n```",
        glossary="# Glossary\n\n- **Foo** \u2014 a test term.",
        dependency_interfaces={},
        module_names=["foo"],
    )


def test_ac_author_019_seed_not_forwarded_to_backend(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    monkeypatch.chdir(tmp_path)

    calls = []

    def spy_backend(*args, **kwargs):
        calls.append((args, dict(kwargs)))
        prompt = args[0] if args else kwargs.get("prompt", "")
        model = args[1] if len(args) > 1 else kwargs.get("model", "")
        m = re.search(r"-----BEGIN FILE ([0-9a-f]{32})-----", prompt)
        if m is None:
            m = re.search(r"\b([0-9a-f]{32})\b", prompt)
        nonce = m.group(1) if m else ""
        text = (
            "-----BEGIN FILE " + nonce + "-----\n"
            "import foo\n\n\ndef test_x():\n    assert foo.foo(2) == 4\n"
            "-----END FILE " + nonce + "-----"
        )
        return {
            "text": text,
            "model": model,
            "backend": "spy",
            "model_call_error": None,
        }

    model = "claude-sonnet-5"
    result = test_author.author_test(
        _make_bundle(), model, 7, repo_root=tmp_path, llm_backend=spy_backend
    )

    assert calls, "the spy backend was never called"
    for args, kwargs in calls:
        assert len(args) == 2, "expected exactly prompt and model positionally, got %r" % (args,)
        assert isinstance(args[0], str) and args[0]
        assert args[1] == model
        assert "seed" not in kwargs, "seed must not be forwarded: %r" % (kwargs,)
        assert "prompt" not in kwargs and "model" not in kwargs

    assert field(result, "model_call_error") is None