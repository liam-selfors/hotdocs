# hotdocs-criterion: sha256:2661491a3726dc87d0a772fce8585cbd6cc854422aebc72adb032dd0725d5e52
import re

import pytest

import generator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


class FakeBundle:
    """An object carrying the SpecBundle fields, readable both as attributes
    and as a read-only mapping, the way SpecBundle itself is."""

    _FIELDS = (
        "component_id",
        "spec_bundle_hash",
        "spec",
        "interface",
        "constraints",
        "dependency_interfaces",
        "dependency_context",
        "dependency_usage",
        "vars",
        "glossary",
        "hint_code",
    )

    def __init__(self, **kwargs):
        for name in self._FIELDS:
            setattr(self, name, kwargs[name])

    def __getitem__(self, key):
        if key not in self._FIELDS:
            raise KeyError(key)
        return getattr(self, key)

    def get(self, key, default=None):
        if key not in self._FIELDS:
            return default
        return getattr(self, key)

    def keys(self):
        return list(self._FIELDS)

    def __iter__(self):
        return iter(self._FIELDS)

    def __len__(self):
        return len(self._FIELDS)

    def __contains__(self, key):
        return key in self._FIELDS


def make_bundle(spec_bundle_hash):
    return FakeBundle(
        component_id="comp-foo",
        spec_bundle_hash=spec_bundle_hash,
        spec="# Foo\n\n## Purpose\n\nFoo doubles a number.\n\n# R-FOO-001\n\n**R-FOO-001** — `foo(x)` MUST return `2 * x`.",
        interface="# Library\n\n```\nfoo(x: int) -> int\n```",
        constraints="# Constraints\n\nNone.",
        dependency_interfaces={},
        dependency_context={},
        dependency_usage={},
        vars={},
        glossary="# Glossary\n\n- **Foo** — a test term.",
        hint_code=None,
    )


def make_backend(calls):
    def backend(prompt, model, **params):
        calls.append(model)
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


@pytest.mark.parametrize(
    "bundle_hash",
    [
        "sha256:" + "a1" * 32,
        "sha256:" + "0123456789abcdef" * 4,
    ],
)
def test_generation_result_echoes_bundle_spec_bundle_hash(tmp_path, monkeypatch, bundle_hash):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    monkeypatch.chdir(tmp_path)

    bundle = make_bundle(bundle_hash)
    calls = []

    result = generator.generate(
        bundle,
        "mock-model",
        None,
        repo_root=tmp_path,
        llm_backend=make_backend(calls),
    )

    # The mock model was reached and produced a usable candidate.
    assert len(calls) == 1
    files = field(result, "files")
    assert files, "expected non-empty files from a valid mock reply"
    assert field(result, "model_call_error") is None
    assert field(result, "refused") is None

    # Then: spec_bundle_hash equals the bundle's own, exactly.
    assert field(result, "spec_bundle_hash") == bundle_hash
    assert field(result, "spec_bundle_hash") == bundle.spec_bundle_hash
    assert isinstance(field(result, "spec_bundle_hash"), str)


def test_distinct_bundle_hashes_are_each_echoed_exactly(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    monkeypatch.chdir(tmp_path)

    hash_one = "sha256:" + "1" * 64
    hash_two = "sha256:" + "2" * 64

    calls = []
    backend = make_backend(calls)

    result_one = generator.generate(
        make_bundle(hash_one), "mock-model", None, repo_root=tmp_path, llm_backend=backend
    )
    result_two = generator.generate(
        make_bundle(hash_two), "mock-model", None, repo_root=tmp_path, llm_backend=backend
    )

    assert field(result_one, "files")
    assert field(result_two, "files")
    assert field(result_one, "spec_bundle_hash") == hash_one
    assert field(result_two, "spec_bundle_hash") == hash_two