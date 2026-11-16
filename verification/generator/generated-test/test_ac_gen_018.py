"""AC-GEN-018 (R-GEN-017): GenerationResult.spec_bundle_hash echoes the bundle's own."""

import importlib.util
import json
import re
import sys
from dataclasses import dataclass, field as dc_field, fields as dc_fields
from pathlib import Path

import generator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _tool_root():
    here = Path(generator.__file__).resolve()
    for p in here.parents:
        if p.name == "gen":
            return p.parent
    return None


def _load_module_from(path, module_name):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _load_spec_bundle_class():
    root = _tool_root()
    if root is None:
        return None
    base = root / "gen" / "spec-bundle-assembler"
    flat = base / "spec_bundle_assembler.py"
    pkg = base / "spec_bundle_assembler" / "__init__.py"
    path = flat if flat.is_file() else (pkg if pkg.is_file() else None)
    if path is None:
        return None
    try:
        mod = sys.modules.get("spec_bundle_assembler")
        if mod is None or not hasattr(mod, "SpecBundle"):
            mod = _load_module_from(path, "spec_bundle_assembler")
        return getattr(mod, "SpecBundle", None)
    except Exception:
        return None


@dataclass(frozen=True)
class _FallbackSpecBundle:
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
    hint_code: object = None

    def __getitem__(self, key):
        if key not in {f.name for f in dc_fields(self)}:
            raise KeyError(key)
        return getattr(self, key)

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default

    def keys(self):
        return [f.name for f in dc_fields(self)]

    def __iter__(self):
        return iter(self.keys())

    def __len__(self):
        return len(self.keys())


KNOWN_HASH = "sha256:" + "5e" * 32


def _make_bundle():
    kwargs = dict(
        component_id="comp-foo",
        spec_bundle_hash=KNOWN_HASH,
        spec="# Foo\n\n## Purpose\n\nFoo doubles a number.\n\n"
        "# R-FOO-001\n\n**R-FOO-001** — `foo(x)` MUST return `2 * x`.",
        interface="# Library\n\n```\nfoo(x: int) -> int\n```",
        constraints="None.",
        dependency_interfaces={},
        dependency_context={},
        dependency_usage={},
        vars={},
        glossary="# Glossary\n\n- **Foo** — a test term.",
        hint_code=None,
    )
    cls = _load_spec_bundle_class()
    if cls is not None:
        try:
            return cls(**kwargs)
        except Exception:
            pass
    return _FallbackSpecBundle(**kwargs)


def test_ac_gen_018_spec_bundle_hash_echoed(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    workdir = tmp_path / "work"
    workdir.mkdir()
    monkeypatch.chdir(workdir)
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)

    log_path = tmp_path / "mock_calls.jsonl"

    def mock_backend(prompt, model, **params):
        nonce = re.search(r"-----BEGIN FILE ([0-9a-f]{32}):", prompt).group(1)
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"model": model, "nonce": nonce}) + "\n")
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

    bundle = _make_bundle()
    bundle_hash = (
        bundle["spec_bundle_hash"] if isinstance(bundle, dict) else bundle.spec_bundle_hash
    )
    assert bundle_hash == KNOWN_HASH

    result = generator.generate(
        bundle,
        "claude-sonnet-5",
        repo_root=repo_root,
        llm_backend=mock_backend,
    )

    # The mock model was actually reached and produced a usable candidate.
    assert log_path.is_file(), "mock llm_backend was never invoked"
    assert field(result, "model_call_error") is None
    assert field(result, "refused") is None
    assert field(result, "files"), "expected a non-empty files candidate"

    # Then: spec_bundle_hash equals the bundle's own, exactly.
    got = field(result, "spec_bundle_hash")
    assert isinstance(got, str)
    assert got == bundle_hash
    assert got == KNOWN_HASH