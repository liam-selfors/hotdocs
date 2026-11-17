# hotdocs-criterion: sha256:08b36bfa1c8666da22c7d46d1b524dfe0e3a9d9cf17973bf34ccd3b45b86dcea
import re
from dataclasses import dataclass, field as dc_field
from pathlib import Path

import test_author


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def body(content):
    first, _, rest = content.partition("\n")
    return rest if first.startswith("# hotdocs-criterion:") else content


@dataclass
class Bundle:
    component_id: str
    criterion_id: str
    covers: str
    criterion_text: str
    requirement_text: str
    interface: str
    glossary: str = ""
    dependency_interfaces: dict = dc_field(default_factory=dict)
    module_names: list = dc_field(default_factory=list)

    def __getitem__(self, key):
        try:
            return getattr(self, key)
        except AttributeError:
            raise KeyError(key)

    def get(self, key, default=None):
        return getattr(self, key, default)

    def keys(self):
        return [
            "component_id",
            "criterion_id",
            "covers",
            "criterion_text",
            "requirement_text",
            "interface",
            "glossary",
            "dependency_interfaces",
            "module_names",
        ]


NONCE_RE = re.compile(r"-----BEGIN FILE ([0-9a-f]+)-----")


def make_backend(log_path, extracted):
    def backend(prompt, model, **params):
        with open(log_path, "a") as fh:
            fh.write("called\n")
        m = NONCE_RE.search(prompt)
        n = m.group(1) if m else "0" * 32
        text = "-----BEGIN FILE " + n + "-----\n" + extracted + "\n-----END FILE " + n + "-----"
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    return backend


def make_bundle():
    return Bundle(
        component_id="comp-foo",
        criterion_id="AC-FOO-001",
        covers="R-FOO-001",
        criterion_text=(
            "# AC-FOO-001\n\nCovers: R-FOO-001\nKind: generated-test\n\n"
            "```gherkin\nGiven x = 2\nWhen foo(x) is called\nThen it returns 4\n```\n"
        ),
        requirement_text="# R-FOO-001\n\n**R-FOO-001** — `foo(x)` MUST return `2 * x`.",
        interface="# Library\n\n```\nfoo(x: int) -> int\n```",
        glossary="# Glossary\n\n- **Foo** — a test term.",
        dependency_interfaces={},
        module_names=["foo"],
    )


def test_cached_result_returned_and_model_never_called(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    monkeypatch.chdir(repo_root)

    model = "claude-sonnet-5"
    cached_body = "import foo\n\n\ndef test_foo():\n    assert foo.foo(2) == 4"

    # Pre-populate the cache-manager store for this criterion + model by a
    # first authoring call through a mock model.
    populate_log = tmp_path / "populate_calls.log"
    first = test_author.author_test(
        make_bundle(),
        model,
        0,
        repo_root=repo_root,
        llm_backend=make_backend(populate_log, cached_body),
    )
    assert field(first, "model_call_error") is None
    assert populate_log.read_text().count("called") >= 1
    assert body(field(field(first, "file"), "content")) == cached_body

    # Now call with matching inputs and a mock that must never be called.
    second_log = tmp_path / "second_calls.log"
    other_body = "import foo\n\n\ndef test_other():\n    assert False"
    second = test_author.author_test(
        make_bundle(),
        model,
        0,
        repo_root=repo_root,
        llm_backend=make_backend(second_log, other_body),
    )

    assert not second_log.exists() or second_log.read_text() == ""
    assert field(second, "cache_hit") is True
    assert field(second, "model_call_error") is None
    assert field(second, "model") == model
    assert field(second, "criterion_id") == "AC-FOO-001"
    assert field(second, "component_id") == "comp-foo"
    assert body(field(field(second, "file"), "content")) == cached_body