"""AC-GEN-004 (Covers: R-GEN-004).

Given the same SpecBundle and two different model identifiers
When generate is called once with each
Then the mock model recorded for each call receives the model identifier
  passed to that call, not a hardcoded default
"""

import generator

import dataclasses
import hashlib
import importlib.util
import json
import re
import sys
from collections.abc import Mapping
from pathlib import Path

import pytest


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


@dataclasses.dataclass(eq=False)
class _FallbackSpecBundle(Mapping):
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

    def __getitem__(self, key):
        names = [f.name for f in dataclasses.fields(self)]
        if key not in names:
            raise KeyError(key)
        return getattr(self, key)

    def __iter__(self):
        return iter([f.name for f in dataclasses.fields(self)])

    def __len__(self):
        return len(dataclasses.fields(self))


def _load_real_spec_bundle_class():
    """Try to use spec-bundle-assembler's own SpecBundle; fall back otherwise."""
    try:
        here = Path(generator.__file__).resolve()
        gen = next(p for p in here.parents if p.name == "gen")
        base = gen / "spec-bundle-assembler"
        flat = base / "spec_bundle_assembler.py"
        pkg = base / "spec_bundle_assembler" / "__init__.py"
        path = flat if flat.is_file() else pkg
        if not path.is_file():
            return None
        module_name = "_ac_gen_004_spec_bundle_assembler"
        spec = importlib.util.spec_from_file_location(module_name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        return getattr(module, "SpecBundle", None)
    except Exception:
        return None


def _make_bundle():
    kwargs = dict(
        component_id="comp-foo",
        spec_bundle_hash="sha256:" + hashlib.sha256(b"ac-gen-004-bundle").hexdigest(),
        spec="# Foo\n\n## Purpose\n\nFoo doubles a number.\n\n"
        "# R-FOO-001\n\n**R-FOO-001** \u2014 `foo(x)` MUST return `2 * x`.",
        interface="# Library\n\n```\nfoo(x: int) -> int\n```",
        constraints="None.",
        dependency_interfaces={},
        dependency_context={},
        dependency_usage={},
        vars={},
        glossary="# Glossary\n\n- **Foo** \u2014 a test term.",
        hint_code=None,
    )
    cls = _load_real_spec_bundle_class()
    if cls is not None:
        try:
            return cls(**kwargs)
        except Exception:
            pass
    return _FallbackSpecBundle(**kwargs)


def _make_backend(log_path: Path):
    def backend(prompt, model, **params):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"model": model}) + "\n")
        nonce = re.search(r"-----BEGIN FILE ([0-9a-f]{32}):", prompt).group(1)
        text = (
            f"-----BEGIN FILE {nonce}: foo.py-----\n"
            "def foo(x):\n"
            "    return 2 * x\n"
            f"-----END FILE {nonce}-----\n"
            f"-----END REPLY {nonce}-----\n"
        )
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    return backend


def test_model_identifier_passed_through_to_mock_model(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    workdir = tmp_path / "cwd"
    workdir.mkdir()
    monkeypatch.chdir(workdir)

    bundle = _make_bundle()
    model_a = "mock-model-alpha-ac-gen-004"
    model_b = "mock-model-beta-ac-gen-004"
    assert model_a != model_b

    log_a = tmp_path / "calls_a.jsonl"
    log_b = tmp_path / "calls_b.jsonl"

    result_a = generator.generate(
        bundle, model_a, repo_root=repo_root, llm_backend=_make_backend(log_a)
    )
    result_b = generator.generate(
        bundle, model_b, repo_root=repo_root, llm_backend=_make_backend(log_b)
    )

    assert log_a.is_file(), "mock model was never called for the first generate"
    assert log_b.is_file(), "mock model was never called for the second generate"

    calls_a = [json.loads(line) for line in log_a.read_text().splitlines() if line.strip()]
    calls_b = [json.loads(line) for line in log_b.read_text().splitlines() if line.strip()]

    assert len(calls_a) == 1
    assert len(calls_b) == 1
    assert calls_a[0]["model"] == model_a
    assert calls_b[0]["model"] == model_b

    # Each call's result reflects the model it was given, not a default.
    assert field(result_a, "model") == model_a
    assert field(result_b, "model") == model_b
    assert field(result_a, "model_call_error") is None
    assert field(result_b, "model_call_error") is None
    assert field(result_a, "cache_hit") is False
    assert field(result_b, "cache_hit") is False