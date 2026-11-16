import importlib.util
import json
import re
import sys
from dataclasses import dataclass, field as dc_field
from pathlib import Path

import pytest

import generator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


@dataclass
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
        try:
            return getattr(self, key)
        except AttributeError:
            raise KeyError(key)

    def get(self, key, default=None):
        return getattr(self, key, default)

    def keys(self):
        return list(self.__dataclass_fields__.keys())

    def __iter__(self):
        return iter(self.keys())

    def __len__(self):
        return len(self.keys())


def _load_spec_bundle_class():
    """Use the real SpecBundle dataclass from the tool's spec-bundle-assembler when available."""
    try:
        gen_dir = next(
            p for p in Path(generator.__file__).resolve().parents if p.name == "gen"
        )
        base = gen_dir / "spec-bundle-assembler"
        flat = base / "spec_bundle_assembler.py"
        pkg = base / "spec_bundle_assembler" / "__init__.py"
        path = flat if flat.is_file() else pkg
        if not path.is_file():
            return _FallbackSpecBundle
        name = "spec_bundle_assembler"
        if name in sys.modules and hasattr(sys.modules[name], "SpecBundle"):
            return sys.modules[name].SpecBundle
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        cls = getattr(module, "SpecBundle", None)
        return cls if cls is not None else _FallbackSpecBundle
    except Exception:
        return _FallbackSpecBundle


def _make_bundle():
    kwargs = dict(
        component_id="comp-foo-bar",
        spec_bundle_hash="sha256:" + "ab" * 32,
        spec="# Foo Bar\n\n## Purpose\n\nFoo bar doubles a number.\n\n"
        "# R-FOO-BAR-001\n\n**R-FOO-BAR-001** — `foo_bar(x)` MUST return `2 * x`.",
        interface="# Library\n\n```\nfoo_bar(x: int) -> int\n```",
        constraints="None.",
        dependency_interfaces={},
        dependency_context={},
        dependency_usage={},
        vars={},
        glossary="- **Foo** — a test term.",
        hint_code=None,
    )
    cls = _load_spec_bundle_class()
    try:
        return cls(**kwargs)
    except Exception:
        return _FallbackSpecBundle(**kwargs)


def test_ac_gen_021_redundant_component_prefix_stripped(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    work = tmp_path / "work"
    work.mkdir()
    log_path = tmp_path / "backend_calls.jsonl"

    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    monkeypatch.chdir(work)

    returned_paths = [
        "foo-bar/foo_bar.py",
        "gen/foo-bar/helpers/__init__.py",
        "foo_bar_extra.py",
    ]
    contents = {
        "foo-bar/foo_bar.py": "def foo_bar(x):\n    return 2 * x\n",
        "gen/foo-bar/helpers/__init__.py": "HELPER = 1\n",
        "foo_bar_extra.py": "EXTRA = 2\n",
    }

    def mock_backend(prompt, model, **params):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"model": model}) + "\n")
        nonce = re.search(r"-----BEGIN FILE ([0-9a-f]{32}):", prompt).group(1)
        parts = ["Here are the files.\n"]
        for p in returned_paths:
            parts.append(f"-----BEGIN FILE {nonce}: {p}-----\n")
            parts.append(contents[p])
            parts.append(f"-----END FILE {nonce}-----\n")
        parts.append(f"-----END REPLY {nonce}-----\n")
        return {
            "text": "".join(parts),
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    bundle = _make_bundle()
    result = generator.generate(
        bundle, "claude-sonnet-5", repo_root=repo_root, llm_backend=mock_backend
    )

    # The mock was actually called (cold, unsealed, cache miss).
    assert log_path.is_file(), "mock llm backend was never invoked"
    assert field(result, "model_call_error") is None
    assert field(result, "refused") is None
    assert field(result, "files")

    out = repo_root / "gen" / "foo-bar"
    assert (out / "foo_bar.py").is_file()
    assert (out / "helpers" / "__init__.py").is_file()
    assert (out / "foo_bar_extra.py").is_file()

    assert (out / "foo_bar.py").read_text(encoding="utf-8") == contents["foo-bar/foo_bar.py"]
    assert (out / "helpers" / "__init__.py").read_text(encoding="utf-8") == contents[
        "gen/foo-bar/helpers/__init__.py"
    ]
    assert (out / "foo_bar_extra.py").read_text(encoding="utf-8") == contents["foo_bar_extra.py"]

    assert not (out / "foo-bar").exists(), "nothing may be written under gen/foo-bar/foo-bar/"
    assert not (out / "gen").exists(), "nothing may be written under gen/foo-bar/gen/"