"""AC-GEN-003: every GenerationResult's prompt_version matches the frozen
prompt template's declared version (generator.PROMPT_VERSION, "v11")."""

import hashlib
import json
import re
from dataclasses import dataclass, field as dc_field, fields as dc_fields

import pytest

import generator


DECLARED_PROMPT_VERSION = "v11"


def _get(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


@dataclass
class SpecBundle:
    """A SpecBundle-shaped value: the documented fields, in order, that also
    reads as a read-only mapping."""

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

    def _names(self):
        return [f.name for f in dc_fields(self)]

    def __getitem__(self, key):
        if key not in self._names():
            raise KeyError(key)
        return getattr(self, key)

    def get(self, key, default=None):
        if key not in self._names():
            return default
        return getattr(self, key)

    def keys(self):
        return list(self._names())

    def items(self):
        return [(k, getattr(self, k)) for k in self._names()]

    def values(self):
        return [getattr(self, k) for k in self._names()]

    def __iter__(self):
        return iter(self._names())

    def __len__(self):
        return len(self._names())

    def __contains__(self, key):
        return key in self._names()


def _hash(text):
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def _make_backend(log_path, valid=True):
    def backend(prompt, model, **params):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"model": model}) + "\n")
        match = re.search(r"-----BEGIN FILE ([0-9a-f]{32}):", prompt)
        if valid and match is not None:
            nonce = match.group(1)
            text = (
                f"-----BEGIN FILE {nonce}: foo.py-----\n"
                "def foo(x):\n"
                "    return 2 * x\n"
                f"-----END FILE {nonce}-----\n"
                f"-----END REPLY {nonce}-----\n"
            )
        else:
            text = "no file blocks here at all"
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    return backend


def _bundle(variant):
    spec = (
        "# Foo\n\n## Purpose\n\nFoo doubles a number.\n\n"
        "# R-FOO-001\n\n**R-FOO-001** — `foo(x)` MUST return `2 * x`."
    )
    interface = "# Library\n\n```\nfoo(x: int) -> int\n```"
    if variant == "minimal":
        return SpecBundle(
            component_id="comp-foo",
            spec_bundle_hash=_hash("minimal" + spec),
            spec=spec,
            interface=interface,
            constraints="# Constraints\n\nNone.",
        )
    if variant == "rich":
        return SpecBundle(
            component_id="comp-foo",
            spec_bundle_hash=_hash("rich" + spec),
            spec=spec,
            interface=interface,
            constraints="# Constraints\n\nNone.",
            dependency_interfaces={"comp-bar": "# Library\n\n```\nbar() -> int\n```"},
            dependency_context={"comp-bar": "Bar returns a number."},
            dependency_usage={"comp-bar": ""},
            vars={"VAR-FOO-URL": "The URL foo reads."},
            glossary="# Glossary\n\n- **Foo** — a test term.",
        )
    if variant == "hint":
        return SpecBundle(
            component_id="comp-foo",
            spec_bundle_hash=_hash("hint" + spec),
            spec=spec,
            interface=interface,
            constraints="# Constraints\n\nNone.",
            glossary="# Glossary\n\n- **Foo** — a test term.",
            hint_code={"foo.py": "def foo(x):\n    return x + x\n"},
        )
    raise AssertionError(variant)


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    work = tmp_path / "cwd"
    work.mkdir()
    monkeypatch.chdir(work)
    log_path = tmp_path / "backend_calls.jsonl"
    return repo_root, log_path


def test_declared_prompt_version_is_frozen():
    assert generator.PROMPT_VERSION == DECLARED_PROMPT_VERSION


@pytest.mark.parametrize("variant", ["minimal", "rich", "hint"])
@pytest.mark.parametrize("retry_feedback", [None, ["R-FOO-001"]])
def test_prompt_version_matches_declared_version(env, variant, retry_feedback):
    repo_root, log_path = env
    bundle = _bundle(variant)

    result = generator.generate(
        bundle,
        "mock:model-a",
        retry_feedback,
        repo_root=repo_root,
        llm_backend=_make_backend(log_path),
    )

    assert log_path.is_file(), "the mock model backend was never called"
    assert _get(result, "files"), "expected a usable candidate from the mock reply"
    assert _get(result, "prompt_version") == generator.PROMPT_VERSION
    assert _get(result, "prompt_version") == DECLARED_PROMPT_VERSION


def test_prompt_version_matches_on_cache_hit(env):
    repo_root, log_path = env
    bundle = _bundle("rich")
    backend = _make_backend(log_path)

    first = generator.generate(
        bundle, "mock:model-a", repo_root=repo_root, llm_backend=backend
    )
    assert _get(first, "files")
    assert _get(first, "prompt_version") == generator.PROMPT_VERSION
    generator.commit_cache(first, repo_root=repo_root)

    second = generator.generate(
        bundle, "mock:model-a", repo_root=repo_root, llm_backend=backend
    )
    assert _get(second, "cache_hit") is True
    assert _get(second, "prompt_version") == generator.PROMPT_VERSION
    assert _get(second, "prompt_version") == DECLARED_PROMPT_VERSION


def test_prompt_version_matches_on_model_call_error(env):
    repo_root, log_path = env
    bundle = _bundle("minimal")

    result = generator.generate(
        bundle,
        "mock:model-a",
        repo_root=repo_root,
        llm_backend=_make_backend(log_path, valid=False),
    )

    assert log_path.is_file(), "the mock model backend was never called"
    assert _get(result, "model_call_error") is not None
    assert _get(result, "prompt_version") == generator.PROMPT_VERSION
    assert _get(result, "prompt_version") == DECLARED_PROMPT_VERSION