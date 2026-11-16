import dataclasses
import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest

import generator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


@dataclasses.dataclass
class _LocalSpecBundle:
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
    hint_code: dict = None

    def __getitem__(self, key):
        if key not in self.keys():
            raise KeyError(key)
        return getattr(self, key)

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default

    def keys(self):
        return [f.name for f in dataclasses.fields(self)]

    def __iter__(self):
        return iter(self.keys())

    def __len__(self):
        return len(self.keys())

    def __contains__(self, key):
        return key in self.keys()


def _spec_bundle_class():
    """Prefer the real SpecBundle from the tool's spec-bundle-assembler; else a
    local dataclass with the documented fields, order, and mapping access."""
    try:
        gen = next(
            p for p in Path(generator.__file__).resolve().parents if p.name == "gen"
        )
        base = gen / "spec-bundle-assembler"
        path = base / "spec_bundle_assembler.py"
        if not path.is_file():
            path = base / "spec_bundle_assembler" / "__init__.py"
        if not path.is_file():
            return _LocalSpecBundle
        module_name = "spec_bundle_assembler"
        spec = importlib.util.spec_from_file_location(module_name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        cls = getattr(module, "SpecBundle", None)
        return cls if cls is not None else _LocalSpecBundle
    except Exception:
        return _LocalSpecBundle


SPEC_MARK = "SPECMARK_7a1c3e"
INTERFACE_MARK = "IFACEMARK_b29d40"
CONSTRAINTS_MARK = "CONSTRMARK_c58e11"
DEPIFACE_MARK = "DEPIFACEMARK_d03f72"
VARS_MARK = "VARSMARK_e64a93"
GLOSSARY_MARK = "GLOSSMARK_f15b24"
STALE_MARK = "STALEGENMARK_0a9c55"


def _make_bundle():
    cls = _spec_bundle_class()
    return cls(
        component_id="comp-foo",
        spec_bundle_hash="sha256:" + "ab" * 32,
        spec=(
            "# Foo\n\n## Purpose\n\nFoo doubles a number. " + SPEC_MARK + "\n\n"
            "# R-FOO-001\n\n**R-FOO-001** — `foo(x)` MUST return `2 * x`."
        ),
        interface="# Library\n\n```\nfoo(x: int) -> int\n```\n\n" + INTERFACE_MARK,
        constraints="# Constraints\n\nNone. " + CONSTRAINTS_MARK,
        dependency_interfaces={"comp-bar": "# Library\n\nbar() -> None " + DEPIFACE_MARK},
        dependency_context={},
        dependency_usage={},
        vars={"VAR-FOO-URL": "The foo service URL. " + VARS_MARK},
        glossary="# Glossary\n\n- **Foo** — a test term. " + GLOSSARY_MARK,
        hint_code=None,
    )


def _make_backend(log_path):
    def backend(prompt, model, **params):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"prompt": prompt, "model": model}) + "\n")
        match = re.search(r"-----BEGIN FILE ([0-9a-f]{32}):", prompt)
        nonce = match.group(1) if match else "0" * 32
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


def _read_log(log_path):
    lines = [l for l in Path(log_path).read_text(encoding="utf-8").splitlines() if l.strip()]
    return [json.loads(l) for l in lines]


def _normalize(prompt):
    match = re.search(r"-----BEGIN FILE ([0-9a-f]{32}):", prompt)
    assert match, "prompt must state this call's nonce in the begin marker"
    return prompt.replace(match.group(1), "NONCE")


def test_cold_generate_prompt_built_from_exactly_bundle_fields(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    monkeypatch.chdir(tmp_path)

    bundle = _make_bundle()
    assert field(bundle, "hint_code") is None  # cold mode

    # Repo A carries stale gen/foo/ content that must never reach the model.
    repo_a = tmp_path / "repo_a"
    stale_dir = repo_a / "gen" / "foo"
    stale_dir.mkdir(parents=True)
    (stale_dir / "foo.py").write_text(
        f"# {STALE_MARK}\ndef foo(x):\n    return 3 * x\n", encoding="utf-8"
    )
    (stale_dir / "helper.py").write_text(f"STALE = '{STALE_MARK}'\n", encoding="utf-8")

    # Repo B is bare.
    repo_b = tmp_path / "repo_b"
    repo_b.mkdir()

    log_a = tmp_path / "calls_a.jsonl"
    log_b = tmp_path / "calls_b.jsonl"

    result_a = generator.generate(
        bundle, "mock-model", repo_root=repo_a, llm_backend=_make_backend(log_a)
    )
    result_b = generator.generate(
        bundle, "mock-model", repo_root=repo_b, llm_backend=_make_backend(log_b)
    )

    # The model was actually called, once each, and produced a candidate.
    for result in (result_a, result_b):
        assert field(result, "cache_hit") is False
        assert field(result, "refused") is None
        assert field(result, "model_call_error") is None
        assert field(result, "files")

    calls_a = _read_log(log_a)
    calls_b = _read_log(log_b)
    assert len(calls_a) == 1
    assert len(calls_b) == 1
    prompt_a = calls_a[0]["prompt"]
    prompt_b = calls_b[0]["prompt"]

    # Contains every one of the six bundle fields.
    for mark in (
        SPEC_MARK,
        INTERFACE_MARK,
        CONSTRAINTS_MARK,
        DEPIFACE_MARK,
        VARS_MARK,
        GLOSSARY_MARK,
    ):
        assert mark in prompt_a, f"{mark} missing from model input"
        assert mark in prompt_b, f"{mark} missing from model input"

    # Nothing else: never the component's current gen/<component>/ content.
    assert STALE_MARK not in prompt_a
    assert "return 3 * x" not in prompt_a

    # Nothing else: the model input depends only on the bundle, not on any
    # repository state -- identical across repos apart from the per-call nonce.
    assert _normalize(prompt_a) == _normalize(prompt_b)