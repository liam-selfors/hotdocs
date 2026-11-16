import dataclasses
import json
import re
import uuid
from pathlib import Path

import pytest

import generator


def _field(value, name):
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


@dataclasses.dataclass
class _SpecBundle:
    component_id: str
    spec_bundle_hash: str
    spec: str
    interface: str
    constraints: str
    dependency_interfaces: dict = dataclasses.field(default_factory=dict)
    dependency_context: dict = dataclasses.field(default_factory=dict)
    dependency_usage: dict = dataclasses.field(default_factory=dict)
    vars: dict = dataclasses.field(default_factory=dict)
    glossary: str = ""
    hint_code: object = None

    def _names(self):
        return [f.name for f in dataclasses.fields(self)]

    def __getitem__(self, key):
        if key in self._names():
            return getattr(self, key)
        raise KeyError(key)

    def get(self, key, default=None):
        if key in self._names():
            return getattr(self, key)
        return default

    def keys(self):
        return list(self._names())

    def items(self):
        return [(k, getattr(self, k)) for k in self._names()]

    def values(self):
        return [getattr(self, k) for k in self._names()]

    def __contains__(self, key):
        return key in self._names()

    def __iter__(self):
        return iter(self._names())

    def __len__(self):
        return len(self._names())


_FAKE_CACHE_MANAGER = '''
import dataclasses
import datetime


class SchemaValidationError(ValueError):
    pass


@dataclasses.dataclass
class CacheKey:
    spec_bundle_hash: str
    gate_inputs_hash: str
    gate_version: str
    model_pin: str


@dataclasses.dataclass
class CachedResult:
    gate_type: str
    payload: dict
    stored_at: str


class Miss:
    def __eq__(self, other):
        return isinstance(other, Miss)

    def __hash__(self):
        return hash("Miss")

    def __repr__(self):
        return "Miss()"


_REQUIRED = {
    "generator": ["component_id", "model", "prompt_version", "files"],
    "compiler": ["outputs", "gate_version", "summary"],
    "generated_test": ["component_id", "criterion_id", "model", "file"],
    "llm_judge": ["result", "rationale"],
    "license_scanner": ["component_id", "gate_version", "similarity_score", "blocked", "matches"],
    "secret_scanner": ["scope", "gate_version", "flagged", "matches"],
}


def _get(obj, name):
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


def get(cache_key, *, repo_root=None):
    return Miss()


def put(cache_key, result, *, repo_root=None):
    gate_version = _get(cache_key, "gate_version") or ""
    key_gate_type = gate_version.split("@", 1)[0]
    gate_type = _get(result, "gate_type")
    if gate_type not in _REQUIRED or gate_type != key_gate_type:
        raise SchemaValidationError("gate type mismatch")
    payload = _get(result, "payload")
    if not isinstance(payload, dict):
        raise SchemaValidationError("payload must be a mapping")
    for k in _REQUIRED[gate_type]:
        if k not in payload:
            raise SchemaValidationError("missing payload key: " + k)
    return None


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def stats(*, repo_root=None):
    return {"entry_count": 0}


def main(argv=None):
    print('{"result": "miss"}')
    return 0
'''


_COMPONENT_MD = """---
id: comp-foo
title: Foo
status: draft
owners: [team-a]
sealed: false
depends_on: []
---

# Foo

## Purpose

Foo doubles a number.
"""


def _write_fixture(repo_root: Path):
    (repo_root / "specs").mkdir(parents=True, exist_ok=True)
    (repo_root / "specs" / "glossary.md").write_text(
        "# Glossary\n\n- **Foo** — a test term.\n", encoding="utf-8"
    )
    comp = repo_root / "specs" / "components" / "foo"
    (comp / "requirements").mkdir(parents=True, exist_ok=True)
    (comp / "acceptance").mkdir(parents=True, exist_ok=True)
    (comp / "interface").mkdir(parents=True, exist_ok=True)
    (comp / "component.md").write_text(_COMPONENT_MD, encoding="utf-8")
    (comp / "requirements" / "R-FOO-001.md").write_text(
        "# R-FOO-001\n\n**R-FOO-001** — `foo(x)` MUST return `2 * x`.\n",
        encoding="utf-8",
    )
    (comp / "acceptance" / "AC-FOO-001.md").write_text(
        "# AC-FOO-001\n\nCovers: R-FOO-001\nKind: generated-test\n\n"
        "```gherkin\nGiven x = 2\nWhen foo(x) is called\nThen it returns 4\n```\n",
        encoding="utf-8",
    )
    (comp / "interface" / "library.md").write_text(
        "# Library\n\n```\nfoo(x: int) -> int\n```\n", encoding="utf-8"
    )
    (comp / "constraints.md").write_text("# Constraints\n\nNone.\n", encoding="utf-8")

    fake_cache_dir = repo_root / "gen" / "cache-manager"
    fake_cache_dir.mkdir(parents=True, exist_ok=True)
    (fake_cache_dir / "cache_manager.py").write_text(_FAKE_CACHE_MANAGER, encoding="utf-8")


def _make_bundle():
    return _SpecBundle(
        component_id="comp-foo",
        spec_bundle_hash="sha256:" + ("ab" * 32),
        spec="# Foo\n\n## Purpose\n\nFoo doubles a number.\n\n# R-FOO-001\n\n"
        "**R-FOO-001** — `foo(x)` MUST return `2 * x`.",
        interface="# Library\n\n```\nfoo(x: int) -> int\n```",
        constraints="# Constraints\n\nNone.",
        dependency_interfaces={},
        dependency_context={},
        dependency_usage={},
        vars={},
        glossary="# Glossary\n\n- **Foo** — a test term.",
        hint_code=None,
    )


def _make_backend(log_path: Path):
    def backend(prompt, model, **params):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"model": model}) + "\n")
        text_prompt = prompt if isinstance(prompt, str) else str(prompt)
        candidates = re.findall(r"BEGIN FILE ([0-9a-f]{32})", text_prompt)
        if not candidates:
            candidates = re.findall(
                r"(?<![0-9a-fA-F])[0-9a-f]{32}(?![0-9a-fA-F])", text_prompt
            )
        nonces = []
        for n in candidates:
            if n not in nonces:
                nonces.append(n)
        blocks = "".join(
            "-----BEGIN FILE {n}: foo.py-----\n"
            "def foo(x):\n"
            "    return 2 * x\n"
            "-----END FILE {n}-----\n".format(n=n)
            for n in nonces
        )
        return {
            "text": "Here is the implementation.\n" + blocks,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    return backend


def _read_models(log_path: Path):
    if not log_path.is_file():
        return []
    models = []
    for line in log_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            models.append(json.loads(line)["model"])
    return models


def test_ac_gen_004_model_identifier_passed_through_unchanged(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write_fixture(repo_root)

    monkeypatch.chdir(repo_root)
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)

    bundle = _make_bundle()

    suffix = uuid.uuid4().hex[:8]
    model_a = "mock-model-alpha-" + suffix
    model_b = "mock-model-beta-" + suffix
    assert model_a != model_b

    log_a = tmp_path / "calls_a.jsonl"
    log_b = tmp_path / "calls_b.jsonl"

    result_a = generator.generate(
        bundle, model_a, repo_root=repo_root, llm_backend=_make_backend(log_a)
    )
    result_b = generator.generate(
        bundle, model_b, repo_root=repo_root, llm_backend=_make_backend(log_b)
    )

    models_a = _read_models(log_a)
    models_b = _read_models(log_b)

    assert models_a, "mock model was never called for the first generate() call"
    assert models_b, "mock model was never called for the second generate() call"

    assert all(m == model_a for m in models_a), (
        "first call's mock model received %r, expected %r" % (models_a, model_a)
    )
    assert all(m == model_b for m in models_b), (
        "second call's mock model received %r, expected %r" % (models_b, model_b)
    )

    assert model_b not in models_a
    assert model_a not in models_b

    assert _field(result_a, "model") == model_a
    assert _field(result_b, "model") == model_b