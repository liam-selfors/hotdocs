import generator

import dataclasses
import importlib.util
import json
import re
import sys
from collections.abc import Mapping
from pathlib import Path

import pytest


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


@dataclasses.dataclass
class _LocalSpecBundle(Mapping):
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
        if key not in {f.name for f in dataclasses.fields(self)}:
            raise KeyError(key)
        return getattr(self, key)

    def __iter__(self):
        return iter([f.name for f in dataclasses.fields(self)])

    def __len__(self):
        return len(dataclasses.fields(self))


def _load_real_spec_bundle_class():
    """Try the tool's own spec-bundle-assembler SpecBundle; else None."""
    try:
        here = Path(generator.__file__).resolve()
        gen_dir = next(p for p in here.parents if p.name == "gen")
        base = gen_dir / "spec-bundle-assembler"
        flat = base / "spec_bundle_assembler.py"
        pkg = base / "spec_bundle_assembler" / "__init__.py"
        path = flat if flat.is_file() else pkg
        if not path.is_file():
            return None
        name = "_ac_gen_020_spec_bundle_assembler"
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        return getattr(module, "SpecBundle", None)
    except Exception:
        return None


def _make_cold_bundle():
    kwargs = dict(
        component_id="comp-foo",
        spec_bundle_hash="sha256:" + "a" * 64,
        spec=(
            "# Foo\n\n## Purpose\n\nFoo doubles a number.\n\n"
            "# R-FOO-001\n\n**R-FOO-001** \u2014 `foo(x)` MUST return `2 * x`."
        ),
        interface="# Library\n\n```\nfoo(x: int) -> int\n```",
        constraints="# Constraints\n\nNone.",
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
    return _LocalSpecBundle(**kwargs)


def test_ac_gen_020_prompt_requires_dual_access_for_dependency_top_level_return(
    tmp_path, monkeypatch
):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.chdir(work)

    log_path = tmp_path / "mock_model_calls.jsonl"

    def mock_backend(prompt, model, **params):
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

    bundle = _make_cold_bundle()
    assert field(bundle, "hint_code") is None  # cold mode

    result = generator.generate(
        bundle, "mock-model", repo_root=repo_root, llm_backend=mock_backend
    )
    assert result is not None

    assert log_path.is_file(), "mock model was never called"
    records = [
        json.loads(line)
        for line in log_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert records, "mock model recorded no input"
    prompt = records[-1]["prompt"]
    assert isinstance(prompt, str) and prompt

    # The bundle has no dependencies at all: the instruction must appear
    # regardless of depends_on.
    lowered = prompt.lower()
    paragraphs = [p for p in re.split(r"\n\s*\n", lowered) if p.strip()]

    def is_dual_access_instruction(text):
        mentions_dependency = "dependenc" in text
        mentions_dict = "dict" in text
        mentions_attr = "attr" in text or "getattr" in text
        mentions_top_level = "top-level" in text or "top level" in text
        mentions_return = "return" in text
        forbids_bare = "bare" in text or "never" in text or "not only" in text
        return (
            mentions_dependency
            and mentions_dict
            and mentions_attr
            and mentions_top_level
            and mentions_return
            and forbids_bare
        )

    matching = [p for p in paragraphs if is_dual_access_instruction(p)]
    if not matching:
        # Fall back to a window-based search in case the instruction is not
        # separated into its own paragraph.
        windows = []
        for m in re.finditer(r"top[- ]level", lowered):
            start = max(0, m.start() - 600)
            windows.append(lowered[start : m.end() + 600])
        matching = [w for w in windows if is_dual_access_instruction(w)]

    assert matching, (
        "prompt does not instruct that values read from a dependency call, "
        "including the dependency's own top-level return value, must use "
        "dual dict-or-attribute access rather than bare attribute access"
    )