"""AC-GEN-009 (covers R-GEN-009): sealed components and pinned overrides are
refused as a precondition, before any model call is attempted.

Given a component marked sealed: true with a source_path, and a second
component with a gen/<component>/.overrides.json listing one pinned file,
when generate is invoked for either component with a mock model that records
whether it was ever called, then the mock model is never called and the
GenerationResult has files empty, model_call_error null, and refused set to a
reason string naming which exemption applied.
"""

import generator

import dataclasses
import hashlib
import json
import re
from pathlib import Path

import pytest


MODEL = "claude-sonnet-5"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


@dataclasses.dataclass
class FakeSpecBundle:
    """A SpecBundle-shaped dataclass (fields in the documented order) that
    also reads as a read-only mapping, as SpecBundle does."""

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
        if key not in {f.name for f in dataclasses.fields(self)}:
            raise KeyError(key)
        return getattr(self, key)

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default

    def keys(self):
        return [f.name for f in dataclasses.fields(self)]

    def __contains__(self, key):
        return key in self.keys()


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _make_bundle(component_id: str, slug: str) -> FakeSpecBundle:
    spec = (
        f"# {slug.title()}\n\n## Purpose\n\n{slug.title()} doubles a number.\n\n"
        f"# R-{slug.upper()}-001\n\n"
        f"**R-{slug.upper()}-001** — `{slug}(x)` MUST return `2 * x`."
    )
    interface = f"# Library\n\n```\n{slug}(x: int) -> int\n```"
    constraints = "# Constraints\n\nNone."
    digest = hashlib.sha256((spec + interface + constraints).encode("utf-8")).hexdigest()
    return FakeSpecBundle(
        component_id=component_id,
        spec_bundle_hash="sha256:" + digest,
        spec=spec,
        interface=interface,
        constraints=constraints,
        glossary="# Glossary\n\n- **Foo** — a test term.",
        hint_code=None,
    )


def _make_mock_backend(log_path: Path):
    """A mock llm_backend matching llm-endpoint's backend shape:
    backend(prompt, model, **params) -> ModelResponse. It appends a record
    to a file the test controls every time it is invoked."""

    def backend(prompt, model, **params):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"called": True, "model": model}) + "\n")
        match = re.search(r"-----BEGIN FILE ([0-9a-f]{32}):", prompt or "")
        nonce = match.group(1) if match else "0" * 32
        text = (
            f"-----BEGIN FILE {nonce}: foo.py-----\n"
            "def foo(x):\n    return 2 * x\n"
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


def _calls(log_path: Path) -> int:
    if not log_path.exists():
        return 0
    return len([l for l in log_path.read_text(encoding="utf-8").splitlines() if l.strip()])


@pytest.fixture
def repo(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    # Keep any stray side effects (e.g. call logs) inside the temp dir.
    monkeypatch.chdir(tmp_path)

    _write(repo_root / "specs" / "glossary.md", "# Glossary\n\n- **Foo** — a test term.\n")

    # Component 1: sealed, with a source_path holding its real code.
    _write(
        repo_root / "specs" / "components" / "foo" / "component.md",
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
        "Foo doubles a number.\n",
    )
    _write(repo_root / "legacy" / "foo" / "foo.py", "def foo(x):\n    return x + x\n")

    # Component 2: not sealed, but with one pinned file in .overrides.json.
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
        "Bar doubles a number.\n",
    )
    _write(repo_root / "gen" / "bar" / "bar.py", "# hand-pinned\ndef bar(x):\n    return 2 * x\n")
    # The overrides file lists exactly one pinned file, bar.py.
    _write(
        repo_root / "gen" / "bar" / ".overrides.json",
        json.dumps({"pinned": ["bar.py"]}, indent=2) + "\n",
    )
    return repo_root


def _assert_refused(result, log_path, expected_keywords):
    assert _calls(log_path) == 0, "mock model was called despite a write exemption"

    files = field(result, "files")
    assert files == {} or not files
    assert files is not None and len(files) == 0

    assert field(result, "model_call_error") is None

    refused = field(result, "refused")
    assert isinstance(refused, str) and refused.strip(), "refused must be a reason string"
    lowered = refused.lower()
    assert any(k in lowered for k in expected_keywords), (
        f"refused reason {refused!r} does not name the exemption ({expected_keywords})"
    )
    assert field(result, "cache_hit") is False
    return refused


def test_sealed_component_is_refused_without_model_call(repo, tmp_path):
    log_path = tmp_path / "sealed_calls.log"
    backend = _make_mock_backend(log_path)
    bundle = _make_bundle("comp-foo", "foo")
    legacy_before = (repo / "legacy" / "foo" / "foo.py").read_text(encoding="utf-8")

    result = generator.generate(bundle, MODEL, repo_root=repo, llm_backend=backend)

    refused = _assert_refused(result, log_path, ["sealed"])
    assert refused == "sealed-component"
    assert field(result, "component_id") == "comp-foo"

    # Nothing was written to the sealed component's source_path or gen/.
    assert (repo / "legacy" / "foo" / "foo.py").read_text(encoding="utf-8") == legacy_before
    assert sorted(p.name for p in (repo / "legacy" / "foo").iterdir()) == ["foo.py"]
    assert not (repo / "gen" / "foo").exists() or not any((repo / "gen" / "foo").iterdir())


def test_pinned_override_is_refused_without_model_call(repo, tmp_path):
    log_path = tmp_path / "pinned_calls.log"
    backend = _make_mock_backend(log_path)
    bundle = _make_bundle("comp-bar", "bar")
    pinned_before = (repo / "gen" / "bar" / "bar.py").read_text(encoding="utf-8")

    result = generator.generate(bundle, MODEL, repo_root=repo, llm_backend=backend)

    refused = _assert_refused(result, log_path, ["pinned", "override"])
    assert refused == "pinned-override"
    assert field(result, "component_id") == "comp-bar"

    # The pinned file was not clobbered.
    assert (repo / "gen" / "bar" / "bar.py").read_text(encoding="utf-8") == pinned_before


def test_reasons_distinguish_the_two_exemptions(repo, tmp_path):
    log_path = tmp_path / "both_calls.log"
    backend = _make_mock_backend(log_path)

    sealed = generator.generate(
        _make_bundle("comp-foo", "foo"), MODEL, repo_root=repo, llm_backend=backend
    )
    pinned = generator.generate(
        _make_bundle("comp-bar", "bar"), MODEL, repo_root=repo, llm_backend=backend
    )

    assert _calls(log_path) == 0
    assert field(sealed, "refused") != field(pinned, "refused")
    assert field(sealed, "refused") == generator.check_write_allowed(
        _make_bundle("comp-foo", "foo"), repo_root=repo
    )
    assert field(pinned, "refused") == generator.check_write_allowed(
        _make_bundle("comp-bar", "bar"), repo_root=repo
    )