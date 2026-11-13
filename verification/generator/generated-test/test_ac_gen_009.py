import hashlib
import json
import os
import re
from dataclasses import dataclass, field, fields
from pathlib import Path

import pytest

import generator


MODEL = "claude-sonnet-5"


@dataclass
class _FakeSpecBundle:
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
        if key not in self._names():
            raise KeyError(key)
        return getattr(self, key)

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


def _field(value, name):
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


GLOSSARY = "# Glossary\n\n- **Foo** — a test term.\n"

FOO_COMPONENT_MD = (
    "---\n"
    "id: comp-foo\n"
    "title: Foo\n"
    "status: draft\n"
    "owners: [team-a]\n"
    "sealed: true\n"
    "source_path: legacy/foo/\n"
    "depends_on: []\n"
    "---\n"
    "\n"
    "# Foo\n"
    "\n"
    "## Purpose\n"
    "\n"
    "Foo doubles a number.\n"
)

BAR_COMPONENT_MD = (
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
    "Bar triples a number.\n"
)

LEGACY_FOO_SOURCE = "def foo(x):\n    return 2 * x\n"
PINNED_BAR_SOURCE = "def bar(x):\n    # hand-pinned\n    return 3 * x\n"


def _build_corpus(repo_root: Path) -> None:
    _write(repo_root / "specs" / "glossary.md", GLOSSARY)

    foo = repo_root / "specs" / "components" / "foo"
    _write(foo / "component.md", FOO_COMPONENT_MD)
    _write(
        foo / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n\n**R-FOO-001** — `foo(x)` MUST return `2 * x`.\n",
    )
    _write(
        foo / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n\nCovers: R-FOO-001\nKind: generated-test\n\n"
        "```gherkin\nGiven x = 2\nWhen foo(x) is called\nThen it returns 4\n```\n",
    )
    _write(foo / "interface" / "library.md", "# Library\n\n```\nfoo(x: int) -> int\n```\n")
    _write(foo / "constraints.md", "# Constraints\n\nNone.\n")
    _write(repo_root / "legacy" / "foo" / "foo.py", LEGACY_FOO_SOURCE)

    bar = repo_root / "specs" / "components" / "bar"
    _write(bar / "component.md", BAR_COMPONENT_MD)
    _write(
        bar / "requirements" / "R-BAR-001.md",
        "# R-BAR-001\n\n**R-BAR-001** — `bar(x)` MUST return `3 * x`.\n",
    )
    _write(
        bar / "acceptance" / "AC-BAR-001.md",
        "# AC-BAR-001\n\nCovers: R-BAR-001\nKind: generated-test\n\n"
        "```gherkin\nGiven x = 2\nWhen bar(x) is called\nThen it returns 6\n```\n",
    )
    _write(bar / "interface" / "library.md", "# Library\n\n```\nbar(x: int) -> int\n```\n")
    _write(bar / "constraints.md", "# Constraints\n\nNone.\n")

    # The pinned override: one file listed in gen/bar/.overrides.json.
    _write(repo_root / "gen" / "bar" / "bar.py", PINNED_BAR_SOURCE)
    _write(
        repo_root / "gen" / "bar" / ".overrides.json",
        json.dumps({"pinned": ["bar.py"], "files": ["bar.py"]}, indent=2) + "\n",
    )


def _bundle_for(component_id: str, repo_root: Path) -> _FakeSpecBundle:
    slug = component_id[len("comp-"):]
    base = repo_root / "specs" / "components" / slug
    component_body = (base / "component.md").read_text(encoding="utf-8").split("---\n", 2)[2].strip()
    reqs = "\n\n".join(
        p.read_text(encoding="utf-8").strip()
        for p in sorted((base / "requirements").glob("*.md"))
    )
    interface = (base / "interface" / "library.md").read_text(encoding="utf-8").strip()
    constraints = (base / "constraints.md").read_text(encoding="utf-8").strip()
    digest = hashlib.sha256(
        (component_id + component_body + reqs + interface + constraints).encode("utf-8")
    ).hexdigest()
    return _FakeSpecBundle(
        component_id=component_id,
        spec_bundle_hash="sha256:" + digest,
        spec=component_body + "\n\n" + reqs,
        interface=interface,
        constraints=constraints,
        glossary=GLOSSARY.strip(),
        hint_code=None,
    )


def _make_recording_backend(log_path: Path, component_slug: str):
    def backend(prompt, model, **params):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"called": True, "model": model}) + "\n")
        m = re.search(r"[0-9a-f]{32}", prompt or "")
        nonce = m.group(0) if m else "0" * 32
        text = (
            f"-----BEGIN FILE {nonce}: {component_slug}.py-----\n"
            "def clobbered():\n    return 'clobbered'\n"
            f"-----END FILE {nonce}-----\n"
        )
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    return backend


def _snapshot(directory: Path) -> dict:
    if not directory.exists():
        return {}
    return {
        str(p.relative_to(directory)): p.read_bytes()
        for p in sorted(directory.rglob("*"))
        if p.is_file()
    }


@pytest.mark.parametrize(
    "component_id, exemption",
    [
        ("comp-foo", "sealed"),
        ("comp-bar", "pinned"),
    ],
)
def test_ac_gen_009_refuses_before_any_model_call(tmp_path, monkeypatch, component_id, exemption):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_corpus(repo_root)

    workdir = tmp_path / "cwd"
    workdir.mkdir()
    monkeypatch.chdir(workdir)
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)

    log_path = tmp_path / "model_calls.log"
    slug = component_id[len("comp-"):]
    backend = _make_recording_backend(log_path, slug)

    legacy_before = _snapshot(repo_root / "legacy")
    gen_before = _snapshot(repo_root / "gen" / slug)

    bundle = _bundle_for(component_id, repo_root)
    result = generator.generate(
        bundle, MODEL, None, repo_root=repo_root, llm_backend=backend
    )

    # The mock model was never called.
    assert not log_path.exists() or log_path.read_text(encoding="utf-8").strip() == "", (
        "model backend was invoked despite a cold-regen exemption"
    )

    # files empty, model_call_error null, refused set to a reason string.
    files = _field(result, "files")
    assert not files, f"expected no files, got {files!r}"
    assert _field(result, "model_call_error") is None
    refused = _field(result, "refused")
    assert isinstance(refused, str) and refused.strip(), f"expected refusal reason, got {refused!r}"
    assert not _field(result, "cache_hit")

    reason = refused.lower()
    if exemption == "sealed":
        assert "seal" in reason, f"sealed refusal reason does not name the exemption: {refused!r}"
    else:
        assert "pin" in reason or "override" in reason, (
            f"pinned-override refusal reason does not name the exemption: {refused!r}"
        )
        assert "seal" not in reason, f"pinned-override refusal misnamed as sealed: {refused!r}"

    # Nothing hands-off was clobbered.
    assert _snapshot(repo_root / "legacy") == legacy_before
    assert _snapshot(repo_root / "gen" / slug) == gen_before
    assert (repo_root / "legacy" / "foo" / "foo.py").read_text(encoding="utf-8") == LEGACY_FOO_SOURCE
    assert (repo_root / "gen" / "bar" / "bar.py").read_text(encoding="utf-8") == PINNED_BAR_SOURCE


def test_ac_gen_009_refusal_reasons_are_distinct(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_corpus(repo_root)

    workdir = tmp_path / "cwd"
    workdir.mkdir()
    monkeypatch.chdir(workdir)
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)

    log_path = tmp_path / "model_calls.log"

    reasons = {}
    for component_id in ("comp-foo", "comp-bar"):
        slug = component_id[len("comp-"):]
        result = generator.generate(
            _bundle_for(component_id, repo_root),
            MODEL,
            None,
            repo_root=repo_root,
            llm_backend=_make_recording_backend(log_path, slug),
        )
        reasons[component_id] = _field(result, "refused")

    assert not log_path.exists() or log_path.read_text(encoding="utf-8").strip() == ""
    assert isinstance(reasons["comp-foo"], str) and reasons["comp-foo"]
    assert isinstance(reasons["comp-bar"], str) and reasons["comp-bar"]
    assert reasons["comp-foo"] != reasons["comp-bar"], (
        f"both exemptions reported the same reason: {reasons!r}"
    )