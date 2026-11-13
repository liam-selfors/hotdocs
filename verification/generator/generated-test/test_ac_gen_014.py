import hashlib
import json
import re
import sys
from collections.abc import Mapping
from dataclasses import dataclass, field, fields
from pathlib import Path

import pytest

import generator


USAGE_MARKER = "ZK41-REAL-SYMBOL"
IFACE_MARKER = "QP88-DEP-CONTRACT"


@dataclass
class FakeSpecBundle(Mapping):
    component_id: str
    spec_bundle_hash: str
    spec: str
    interface: str
    constraints: str
    dependency_interfaces: dict = field(default_factory=dict)
    dependency_context: dict = field(default_factory=dict)
    dependency_usage: dict = field(default_factory=dict)
    vars: dict = field(default_factory=dict)
    glossary: str = ""
    hint_code: object = None

    def _names(self):
        return [f.name for f in fields(self)]

    def __getitem__(self, key):
        if key in self._names():
            return getattr(self, key)
        raise KeyError(key)

    def __iter__(self):
        return iter(self._names())

    def __len__(self):
        return len(self._names())

    def get(self, key, default=None):
        if key in self._names():
            return getattr(self, key)
        return default


def _get(value, name):
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_repo(repo_root: Path) -> None:
    _write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Foo** — a test term.\n",
    )
    _write(
        repo_root / "specs" / "components" / "foo" / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "sealed: false\n"
        "depends_on: [comp-bar]\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Foo doubles a number.\n",
    )
    _write(
        repo_root / "specs" / "components" / "bar" / "component.md",
        "---\n"
        "id: comp-bar\n"
        "title: Bar\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "sealed: false\n"
        "depends_on: []\n"
        "---\n"
        "\n"
        "# Bar\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Bar triples a number.\n",
    )
    # The dependency's real, importable code.
    _write(
        repo_root / "gen" / "bar" / "bar.py",
        "def triple(x: int) -> int:\n"
        "    \"\"\"Return three times x.\"\"\"\n"
        "    return 3 * x\n",
    )


def _make_bundle() -> FakeSpecBundle:
    spec = (
        "# Foo\n\n## Purpose\n\nFoo doubles a number.\n\n"
        "# R-FOO-001\n\n**R-FOO-001** — `foo(x)` MUST return `2 * x`."
    )
    interface = "# Library\n\n```\nfoo(x: int) -> int\n```"
    constraints = "# Constraints\n\nNone."
    dep_iface = (
        "# Library\n\n```\ntriple(x: int) -> int\n```\n\n"
        "Triples a number. [" + IFACE_MARKER + "]"
    )
    dep_usage = (
        "Module: `bar` (gen/bar/bar.py)\n\n"
        "def triple(x: int) -> int:\n"
        "    \"\"\"Return three times x. [" + USAGE_MARKER + "]\"\"\""
    )
    glossary = "# Glossary\n\n- **Foo** — a test term."
    digest = hashlib.sha256(
        json.dumps(
            [spec, interface, constraints, dep_iface, dep_usage, glossary]
        ).encode("utf-8")
    ).hexdigest()
    return FakeSpecBundle(
        component_id="comp-foo",
        spec_bundle_hash="sha256:" + digest,
        spec=spec,
        interface=interface,
        constraints=constraints,
        dependency_interfaces={"comp-bar": dep_iface},
        dependency_context={"comp-bar": "Bar triples a number."},
        dependency_usage={"comp-bar": dep_usage},
        vars={},
        glossary=glossary,
        hint_code=None,
    )


_NONCE_LABELLED = re.compile(r"BEGIN FILE ([0-9a-f]{32})")
_NONCE_BARE = re.compile(r"(?<![0-9a-fA-F])([0-9a-f]{32})(?![0-9a-fA-F])")


def _find_nonce(text: str):
    m = _NONCE_LABELLED.search(text)
    if m:
        return m.group(1)
    m = _NONCE_BARE.search(text)
    if m:
        return m.group(1)
    return "0" * 32


def _make_mock_backend(log_path: Path):
    def backend(*args, **kwargs):
        prompt = args[0] if args else kwargs.get("prompt", "")
        model = args[1] if len(args) > 1 else kwargs.get("model", "")
        extra = [
            v for k, v in kwargs.items()
            if k not in ("prompt", "model") and isinstance(v, str)
        ]
        recorded = str(prompt)
        if extra:
            recorded = recorded + "\n" + "\n".join(extra)
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"input": recorded}) + "\n")
        nonce = _find_nonce(str(prompt))
        text = (
            "-----BEGIN FILE " + nonce + ": foo.py-----\n"
            "def foo(x: int) -> int:\n"
            "    return 2 * x\n"
            "-----END FILE " + nonce + "-----\n"
        )
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    return backend


def _read_calls(log_path: Path):
    if not log_path.is_file():
        return []
    out = []
    for line in log_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line)["input"])
    return out


def test_dependency_usage_is_distinct_labeled_section(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_repo(repo_root)

    work = tmp_path / "cwd"
    work.mkdir()
    monkeypatch.chdir(work)
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)

    log_path = tmp_path / "mock_model_calls.jsonl"
    backend = _make_mock_backend(log_path)
    bundle = _make_bundle()

    result = generator.generate(
        bundle,
        "claude-sonnet-5",
        None,
        repo_root=repo_root,
        llm_backend=backend,
    )

    # Absence of real code for other deps is irrelevant here; this one has
    # real code and generation must not be refused.
    assert _get(result, "refused") is None

    calls = _read_calls(log_path)
    assert calls, "mock model was never called"

    with_usage = [c for c in calls if USAGE_MARKER in c]
    assert with_usage, (
        "dependency_usage content never reached the model's input"
    )
    recorded = with_usage[0]

    assert IFACE_MARKER in recorded, (
        "dependency_interfaces content missing from the model's input"
    )

    u_pos = recorded.index(USAGE_MARKER)
    i_pos = recorded.index(IFACE_MARKER)
    assert u_pos != i_pos

    usage_label = re.compile(r"usage", re.IGNORECASE)
    iface_label = re.compile(r"interface", re.IGNORECASE)

    # A label naming the usage section must precede the usage content.
    usage_labels_before = [
        m.start() for m in usage_label.finditer(recorded, 0, u_pos)
    ]
    assert usage_labels_before, (
        "dependency_usage content is not preceded by any usage label"
    )
    nearest_usage_label = usage_labels_before[-1]
    # The nearest usage label must start a section that does not also
    # contain the dependency_interfaces content (i.e. not merged).
    between = recorded[nearest_usage_label:u_pos]
    assert IFACE_MARKER not in between, (
        "dependency_usage appears merged into the dependency_interfaces "
        "section rather than in its own labeled section"
    )

    if i_pos < u_pos:
        # Interfaces come first: a usage label must open a new section
        # after the interface content and before the usage content.
        assert usage_label.search(recorded, i_pos, u_pos), (
            "no distinct usage section label separates dependency_usage "
            "from dependency_interfaces"
        )
    else:
        # Usage comes first: an interface label must open a new section
        # after the usage content and before the interface content.
        assert iface_label.search(recorded, u_pos, i_pos), (
            "no distinct interfaces section label separates "
            "dependency_interfaces from dependency_usage"
        )