# hotdocs-criterion: sha256:da2a43e0d7b465d3e5593949526e6b3a1a5a46fd753028a7f736a9796ee28a38
import re
from dataclasses import dataclass, field as dc_field

import pytest

import generator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


@dataclass
class FakeSpecBundle:
    component_id: str
    spec_bundle_hash: str
    spec: str
    interface: str
    constraints: str
    dependency_interfaces: dict = dc_field(default_factory=dict)
    dependency_context: dict = dc_field(default_factory=dict)
    dependency_usage: dict = dc_field(default_factory=dict)
    vars: dict = dc_field(default_factory=dict)
    glossary: str = ""
    hint_code: dict = None

    def __getitem__(self, key):
        if key not in self.__dataclass_fields__:
            raise KeyError(key)
        return getattr(self, key)

    def get(self, key, default=None):
        if key not in self.__dataclass_fields__:
            return default
        return getattr(self, key)

    def keys(self):
        return list(self.__dataclass_fields__.keys())

    def __iter__(self):
        return iter(self.keys())

    def __len__(self):
        return len(self.__dataclass_fields__)

    def __contains__(self, key):
        return key in self.__dataclass_fields__


def _bundles():
    return [
        FakeSpecBundle(
            component_id="comp-foo",
            spec_bundle_hash="sha256:" + "a" * 64,
            spec="# Foo\n\n## Purpose\n\nFoo doubles a number.\n\n# R-FOO-001\n\n**R-FOO-001** — `foo(x)` MUST return `2 * x`.",
            interface="# Library\n\n```\nfoo(x: int) -> int\n```",
            constraints="# Constraints\n\nNone.",
            glossary="# Glossary\n\n- **Foo** — a test term.",
        ),
        FakeSpecBundle(
            component_id="comp-bar",
            spec_bundle_hash="sha256:" + "b" * 64,
            spec="# Bar\n\n## Purpose\n\nBar adds one.\n\n# R-BAR-001\n\n**R-BAR-001** — `bar(x)` MUST return `x + 1`.",
            interface="# Library\n\n```\nbar(x: int) -> int\n```",
            constraints="# Constraints\n\nNone.",
            dependency_interfaces={"comp-foo": "# Library\n\n```\nfoo(x: int) -> int\n```"},
            dependency_context={"comp-foo": "Foo doubles a number."},
            dependency_usage={"comp-foo": ""},
            vars={"VAR-BAR-URL": "A URL."},
            glossary="# Glossary\n\n- **Bar** — another test term.",
        ),
        FakeSpecBundle(
            component_id="comp-baz",
            spec_bundle_hash="sha256:" + "c" * 64,
            spec="# Baz\n\n## Purpose\n\nBaz negates.\n\n# R-BAZ-001\n\n**R-BAZ-001** — `baz(x)` MUST return `-x`.",
            interface="# Library\n\n```\nbaz(x: int) -> int\n```",
            constraints="# Constraints\n\nNone.",
            glossary="# Glossary\n\n- **Baz** — a third term.",
            hint_code={"baz.py": "def baz(x):\n    return -x\n"},
        ),
    ]


def _nonce(prompt):
    return re.search(r"-----BEGIN FILE ([0-9a-f]{32}):", prompt).group(1)


def _good_reply(prompt, filename):
    n = _nonce(prompt)
    return (
        "Here is the code.\n"
        + "-----BEGIN FILE " + n + ": " + filename + "-----\n"
        + "def f(x):\n    return x\n"
        + "-----END FILE " + n + "-----\n"
        + "-----END REPLY " + n + "-----\n"
    )


def _make_backend(prompts, reply_fn):
    def backend(prompt, model, **params):
        prompts.append(prompt)
        return {
            "text": reply_fn(prompt),
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }
    return backend


def _declared_version(prompt):
    m = re.search(r"^PROMPT_VERSION: (\S+)\s*$", prompt, re.MULTILINE)
    assert m is not None, "prompt does not declare its PROMPT_VERSION"
    return m.group(1)


@pytest.fixture(autouse=True)
def _isolate(monkeypatch, tmp_path):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    monkeypatch.chdir(tmp_path)


def test_prompt_version_constant_is_documented_value():
    assert generator.PROMPT_VERSION == "v11"


@pytest.mark.parametrize("index", [0, 1, 2])
def test_generated_result_prompt_version_matches_template(tmp_path, index):
    bundle = _bundles()[index]
    prompts = []
    filename = bundle.component_id.replace("comp-", "") + ".py"
    backend = _make_backend(prompts, lambda p: _good_reply(p, filename))

    result = generator.generate(bundle, "mock-model", repo_root=tmp_path, llm_backend=backend)

    assert len(prompts) == 1
    declared = _declared_version(prompts[0])
    assert declared == generator.PROMPT_VERSION
    assert field(result, "prompt_version") == generator.PROMPT_VERSION
    assert field(result, "prompt_version") == declared
    assert field(result, "files"), "expected a candidate from the mock reply"


def test_prompt_version_with_retry_feedback(tmp_path):
    bundle = _bundles()[0]
    prompts = []
    backend = _make_backend(prompts, lambda p: _good_reply(p, "foo.py"))

    result = generator.generate(
        bundle, "mock-model", ["R-FOO-001"], repo_root=tmp_path, llm_backend=backend
    )

    assert len(prompts) == 1
    assert _declared_version(prompts[0]) == generator.PROMPT_VERSION
    assert field(result, "prompt_version") == generator.PROMPT_VERSION


def test_prompt_version_on_rejected_reply(tmp_path):
    bundle = _bundles()[0]
    prompts = []
    backend = _make_backend(prompts, lambda p: "no file blocks here at all")

    result = generator.generate(bundle, "mock-model", repo_root=tmp_path, llm_backend=backend)

    assert field(result, "model_call_error") is not None
    assert field(result, "prompt_version") == generator.PROMPT_VERSION


def test_prompt_version_on_backend_error(tmp_path):
    bundle = _bundles()[1]

    def backend(prompt, model, **params):
        return {
            "text": None,
            "model": model,
            "backend": "mock",
            "model_call_error": {"category": "network", "message": "unreachable"},
        }

    result = generator.generate(bundle, "mock-model", repo_root=tmp_path, llm_backend=backend)

    assert field(result, "model_call_error") is not None
    assert field(result, "prompt_version") == generator.PROMPT_VERSION


def test_prompt_version_on_cache_hit(tmp_path):
    bundle = _bundles()[0]
    prompts = []
    backend = _make_backend(prompts, lambda p: _good_reply(p, "foo.py"))

    first = generator.generate(bundle, "mock-model", repo_root=tmp_path, llm_backend=backend)
    assert field(first, "files")
    generator.commit_cache(first, repo_root=tmp_path)

    second_prompts = []
    backend2 = _make_backend(second_prompts, lambda p: _good_reply(p, "foo.py"))
    second = generator.generate(bundle, "mock-model", repo_root=tmp_path, llm_backend=backend2)

    assert field(second, "cache_hit") is True
    assert second_prompts == []
    assert field(second, "prompt_version") == generator.PROMPT_VERSION