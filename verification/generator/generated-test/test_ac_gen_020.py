"""AC-GEN-020 (covers R-GEN-019).

Given a cold-mode SpecBundle and a mock model that records what it was sent,
when generate is called with that bundle, then the mock model's recorded
input instructs it that any value read from a dependency call, including the
dependency's own top-level return value, must use dual dict-or-attribute
access, never a bare attribute access alone.
"""

import dataclasses
import hashlib
import importlib.util
import json
import re
import sys
import uuid
from pathlib import Path

import pytest

import generator


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------


def _field(value, name, default=None):
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


@dataclasses.dataclass
class _LocalSpecBundle:
    """Fallback SpecBundle matching spec-bundle-assembler's documented
    contract: a dataclass with these fields in this order that also reads
    as a read-only mapping."""

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

    def __iter__(self):
        return iter(self._names())

    def __len__(self):
        return len(self._names())

    def __contains__(self, key):
        return key in self._names()

    @classmethod
    def _names(cls):
        return [f.name for f in dataclasses.fields(cls)]


def _real_spec_bundle_class():
    """Try to obtain the real SpecBundle class from the tool's own
    gen/spec-bundle-assembler/ copy; return None if it is unavailable."""
    try:
        gen = next(
            p for p in Path(generator.__file__).resolve().parents if p.name == "gen"
        )
    except StopIteration:
        return None
    base = gen / "spec-bundle-assembler"
    flat = base / "spec_bundle_assembler.py"
    pkg = base / "spec_bundle_assembler" / "__init__.py"
    path = flat if flat.is_file() else pkg
    if not path.is_file():
        return None
    try:
        module_name = "spec_bundle_assembler"
        spec = importlib.util.spec_from_file_location(module_name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module  # register BEFORE exec_module
        spec.loader.exec_module(module)
        cls = getattr(module, "SpecBundle", None)
        if cls is None or not dataclasses.is_dataclass(cls):
            return None
        return cls
    except Exception:
        return None


def _make_bundle(fields):
    cls = _real_spec_bundle_class()
    if cls is not None:
        try:
            return cls(**fields)
        except Exception:
            pass
    return _LocalSpecBundle(**fields)


def _write(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_repo(repo_root: Path):
    _write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Foo** — a test term.\n",
    )
    comp = repo_root / "specs" / "components" / "foo"
    _write(
        comp / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "sealed: false\n"
        "depends_on: []\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Foo doubles a number.\n",
    )
    _write(
        comp / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n\n**R-FOO-001** — `foo(x)` MUST return `2 * x`.\n",
    )
    _write(
        comp / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n\n"
        "Covers: R-FOO-001\n"
        "Kind: generated-test\n\n"
        "```gherkin\n"
        "Given x = 2\n"
        "When foo(x) is called\n"
        "Then it returns 4\n"
        "```\n",
    )
    _write(
        comp / "interface" / "library.md",
        "# Library\n\n```\nfoo(x: int) -> int\n```\n",
    )
    _write(comp / "constraints.md", "# Constraints\n\nNone.\n")


_ANCHORS = (
    "top-level",
    "top level",
    "toplevel",
    "return value itself",
    "returned value itself",
    "own return value",
    "own returned value",
    "entire return value",
    "whole return value",
)


def _instructs_dual_access_for_top_level(text: str) -> bool:
    norm = re.sub(r"\s+", " ", text.lower())
    window = 1000
    for anchor in _ANCHORS:
        start = 0
        while True:
            idx = norm.find(anchor, start)
            if idx < 0:
                break
            chunk = norm[max(0, idx - window): idx + len(anchor) + window]
            has_dict = "dict" in chunk
            has_attr = ("attribute" in chunk) or ("getattr" in chunk) or ("attr" in chunk)
            has_dep = "dependenc" in chunk
            has_return = "return" in chunk
            has_never_bare = any(
                w in chunk for w in ("bare", "alone", "never", "not only", "only")
            )
            if has_dict and has_attr and has_dep and has_return and has_never_bare:
                return True
            start = idx + 1
    return False


# --------------------------------------------------------------------------
# Test
# --------------------------------------------------------------------------


@pytest.mark.parametrize("with_dependency", [False, True])
def test_prompt_requires_dual_access_for_dependency_top_level_return(
    tmp_path, monkeypatch, with_dependency
):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_repo(repo_root)

    # Keep any call log / local cache writes inside the temp dir and away
    # from a remote cache store.
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)

    log_path = tmp_path / "mock_model_calls.jsonl"
    recorded = []

    def mock_backend(*args, **kwargs):
        prompt = args[0] if args else kwargs.get("prompt", "")
        model = args[1] if len(args) > 1 else kwargs.get("model", "")
        params = {
            k: v for k, v in kwargs.items() if k not in ("prompt", "model")
        }
        entry = {
            "prompt": prompt if isinstance(prompt, str) else str(prompt),
            "params": {k: str(v) for k, v in params.items()},
        }
        recorded.append(entry)
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry) + "\n")

        prompt_text = entry["prompt"]
        m = re.search(r"BEGIN FILE ([0-9a-f]{32})", prompt_text)
        if m is None:
            m = re.search(r"\b([0-9a-f]{32})\b", prompt_text)
        nonce = m.group(1) if m else uuid.uuid4().hex
        reply = (
            f"-----BEGIN FILE {nonce}: foo.py-----\n"
            "def foo(x):\n"
            "    return 2 * x\n"
            f"-----END FILE {nonce}-----\n"
        )
        return {
            "text": reply,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    unique = uuid.uuid4().hex
    dep_interfaces = {}
    dep_context = {}
    dep_usage = {}
    if with_dependency:
        dep_interfaces = {"comp-bar": "# Library\n\n```\nbar(n: int) -> int\n```"}
        dep_context = {"comp-bar": "Bar increments a number."}
        dep_usage = {"comp-bar": ""}

    bundle = _make_bundle(
        {
            "component_id": "comp-foo",
            "spec_bundle_hash": "sha256:"
            + hashlib.sha256(("ac-gen-020-" + unique).encode("utf-8")).hexdigest(),
            "spec": "# Foo\n\n## Purpose\n\nFoo doubles a number.\n\n"
            "# R-FOO-001\n\n**R-FOO-001** — `foo(x)` MUST return `2 * x`.",
            "interface": "# Library\n\n```\nfoo(x: int) -> int\n```",
            "constraints": "# Constraints\n\nNone.",
            "dependency_interfaces": dep_interfaces,
            "dependency_context": dep_context,
            "dependency_usage": dep_usage,
            "vars": {},
            "glossary": "# Glossary\n\n- **Foo** — a test term.",
            "hint_code": None,
        }
    )

    result = generator.generate(
        bundle,
        "anthropic:claude-sonnet-5",
        None,
        repo_root=repo_root,
        llm_backend=mock_backend,
    )

    refused = _field(result, "refused")
    assert refused in (None, ""), f"generation was refused unexpectedly: {refused!r}"
    assert _field(result, "cache_hit") is not True, "unexpected cache hit"

    file_entries = []
    if log_path.is_file():
        for line in log_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                file_entries.append(json.loads(line))
    entries = file_entries or recorded
    assert entries, "the mock model was never called"

    combined = "\n\n".join(
        e["prompt"] + "\n\n" + "\n".join(e["params"].values()) for e in entries
    )

    assert _instructs_dual_access_for_top_level(combined), (
        "the prompt sent to the model does not instruct that values read from "
        "a dependency call — including the dependency's own top-level return "
        "value — must use dual dict-or-attribute access, never a bare "
        "attribute access alone"
    )