import generator

import dataclasses
import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest


HINT_MARKER = "HINT_CODE_MARKER_7f3a91"
SPEC_MARKER = "SPEC_TEXT_MARKER_c04e2b"
INTERFACE_MARKER = "INTERFACE_TEXT_MARKER_5d18aa"
CONSTRAINTS_MARKER = "CONSTRAINTS_TEXT_MARKER_e29f07"
GLOSSARY_MARKER = "GLOSSARY_TEXT_MARKER_b6713c"

HINT_CODE = {
    "foo.py": (
        "def foo(x):\n"
        "    # " + HINT_MARKER + "\n"
        "    return x + x\n"
    )
}


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


@dataclasses.dataclass
class _FallbackSpecBundle:
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
        if key not in self.__dataclass_fields__:
            raise KeyError(key)
        return getattr(self, key)

    def get(self, key, default=None):
        if key in self.__dataclass_fields__:
            return getattr(self, key)
        return default

    def __contains__(self, key):
        return key in self.__dataclass_fields__

    def keys(self):
        return list(self.__dataclass_fields__.keys())


def _load_spec_bundle_class():
    try:
        here = Path(generator.__file__).resolve()
        gen_dir = next(p for p in here.parents if p.name == "gen")
    except (StopIteration, TypeError, AttributeError):
        return None
    base = gen_dir / "spec-bundle-assembler"
    flat = base / "spec_bundle_assembler.py"
    pkg = base / "spec_bundle_assembler" / "__init__.py"
    path = flat if flat.is_file() else pkg
    if not path.is_file():
        return None
    try:
        if "spec_bundle_assembler" in sys.modules:
            mod = sys.modules["spec_bundle_assembler"]
        else:
            spec = importlib.util.spec_from_file_location("spec_bundle_assembler", path)
            mod = importlib.util.module_from_spec(spec)
            sys.modules["spec_bundle_assembler"] = mod
            spec.loader.exec_module(mod)
        return getattr(mod, "SpecBundle", None)
    except Exception:
        return None


def _make_bundle():
    kwargs = dict(
        component_id="comp-foo",
        spec_bundle_hash="sha256:" + "ab" * 32,
        spec="# Foo\n\n## Purpose\n\nFoo doubles a number. " + SPEC_MARKER
        + "\n\n**R-FOO-001** — `foo(x)` MUST return `2 * x`.",
        interface="# Library\n\n```\nfoo(x: int) -> int\n```\n\n" + INTERFACE_MARKER,
        constraints="# Constraints\n\nNone. " + CONSTRAINTS_MARKER,
        dependency_interfaces={},
        dependency_context={},
        dependency_usage={},
        vars={},
        glossary="# Glossary\n\n- **Foo** — a test term. " + GLOSSARY_MARKER,
        hint_code=dict(HINT_CODE),
    )
    cls = _load_spec_bundle_class()
    if cls is not None:
        try:
            return cls(**kwargs)
        except Exception:
            pass
    return _FallbackSpecBundle(**kwargs)


def _make_backend(log_path):
    def backend(prompt, model, **params):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"prompt": prompt, "model": model}) + "\n")
        m = re.search(r"-----BEGIN FILE ([0-9a-f]{32}):", prompt)
        nonce = m.group(1) if m else "0" * 32
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


def test_hint_code_is_distinctly_labeled_section_in_model_input(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_dir = tmp_path / "log"
    log_dir.mkdir()
    log_path = log_dir / "model_calls.jsonl"
    monkeypatch.chdir(repo_root)

    bundle = _make_bundle()

    generator.generate(
        bundle,
        "claude-sonnet-5",
        repo_root=repo_root,
        llm_backend=_make_backend(log_path),
    )

    assert log_path.is_file(), "mock model was never called"
    records = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(records) >= 1
    prompt = records[-1]["prompt"]

    # The recorded input contains the hint code and the cold bundle fields.
    assert HINT_MARKER in prompt
    assert SPEC_MARKER in prompt
    assert INTERFACE_MARKER in prompt

    # The prompt's bundle-derived sections: hint code lives in its own labeled section.
    sections = generator.render_prompt_sections(bundle)
    sections = [(str(t), str(x)) for t, x in sections]
    assert sections, "render_prompt_sections returned no sections"

    hint_sections = [(t, x) for t, x in sections if HINT_MARKER in x or HINT_MARKER in t]
    assert len(hint_sections) >= 1, "hint_code not present in any prompt section"

    cold_markers = (SPEC_MARKER, INTERFACE_MARKER, CONSTRAINTS_MARKER, GLOSSARY_MARKER)
    for title, text in hint_sections:
        assert title.strip(), "hint_code section has no label"
        for marker in cold_markers:
            assert marker not in text, (
                f"hint_code section {title!r} is merged with a cold bundle field ({marker})"
            )
        # The label itself is present in what the model was sent.
        assert title.strip() in prompt, f"hint section label {title!r} not in model input"

    cold_sections = [
        (t, x) for t, x in sections if any(m in x for m in cold_markers)
    ]
    assert cold_sections, "cold bundle fields not present in any prompt section"
    for title, text in cold_sections:
        assert HINT_MARKER not in text, (
            f"cold section {title!r} also contains hint_code"
        )

    hint_titles = {t.strip() for t, _ in hint_sections}
    cold_titles = {t.strip() for t, _ in cold_sections}
    assert hint_titles.isdisjoint(cold_titles), (
        "hint_code section label is not distinct from cold bundle section labels"
    )