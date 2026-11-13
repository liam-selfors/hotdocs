"""AC-GEN-018 (covers R-GEN-017): GenerationResult.spec_bundle_hash MUST
equal the bundle's own spec_bundle_hash exactly."""

import dataclasses
import hashlib
import re
from collections.abc import Mapping
from pathlib import Path

import pytest

import generator


COMPONENT_ID = "comp-foo"
COMPONENT_SLUG = "foo"
MODEL = "claude-sonnet-5"

FILE_PATH = "foo.py"
FILE_CONTENT = "def foo(x: int) -> int:\n    return 2 * x\n"


@dataclasses.dataclass
class FakeSpecBundle(Mapping):
    """Mirrors comp-spec-bundle-assembler's documented SpecBundle: a dataclass
    with these fields in this order that also reads as a read-only mapping."""

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

    def _names(self):
        return [f.name for f in dataclasses.fields(self)]

    def __getitem__(self, key):
        if key in self._names():
            return getattr(self, key)
        raise KeyError(key)

    def __iter__(self):
        return iter(self._names())

    def __len__(self):
        return len(self._names())


def _field(value, name):
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def _make_hash(label: str) -> str:
    return "sha256:" + hashlib.sha256(label.encode("utf-8")).hexdigest()


def _write_component_md(repo_root: Path) -> None:
    comp_dir = repo_root / "specs" / "components" / COMPONENT_SLUG
    comp_dir.mkdir(parents=True, exist_ok=True)
    (comp_dir / "component.md").write_text(
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
        encoding="utf-8",
    )
    glossary = repo_root / "specs" / "glossary.md"
    glossary.parent.mkdir(parents=True, exist_ok=True)
    glossary.write_text("# Glossary\n\n- **Foo** — a test term.\n", encoding="utf-8")


def _make_bundle(spec_bundle_hash: str) -> FakeSpecBundle:
    return FakeSpecBundle(
        component_id=COMPONENT_ID,
        spec_bundle_hash=spec_bundle_hash,
        spec=(
            "# Foo\n\n## Purpose\n\nFoo doubles a number.\n\n"
            "# R-FOO-001\n\n**R-FOO-001** — `foo(x)` MUST return `2 * x`."
        ),
        interface="# Library\n\n```\nfoo(x: int) -> int\n```",
        constraints="# Constraints\n\nNone.",
        glossary="# Glossary\n\n- **Foo** — a test term.",
    )


def _candidate_nonces(prompt: str) -> list:
    found = re.findall(r"(?<![0-9a-fA-F])([0-9a-f]{32})(?![0-9a-fA-F])", prompt)
    seen = []
    for n in found:
        if n not in seen:
            seen.append(n)
    return seen


def _make_backend(calls: list):
    def backend(prompt, model, **params):
        calls.append({"model": model})
        nonces = _candidate_nonces(prompt)
        assert nonces, "prompt did not state a 32-hex nonce for the file markers"
        blocks = []
        for nonce in nonces:
            blocks.append(
                f"-----BEGIN FILE {nonce}: {FILE_PATH}-----\n"
                f"{FILE_CONTENT}"
                f"-----END FILE {nonce}-----\n"
            )
        return {
            "text": "Here is the implementation.\n" + "".join(blocks),
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    return backend


@pytest.fixture
def isolated_env(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    work = tmp_path / "cwd"
    work.mkdir()
    monkeypatch.chdir(work)
    return tmp_path


def _run(repo_root: Path, spec_bundle_hash: str, retry_feedback=None):
    _write_component_md(repo_root)
    bundle = _make_bundle(spec_bundle_hash)
    calls = []
    result = generator.generate(
        bundle,
        MODEL,
        retry_feedback,
        repo_root=repo_root,
        llm_backend=_make_backend(calls),
    )
    return bundle, result, calls


def test_spec_bundle_hash_echoes_bundle_hash_exactly(isolated_env):
    repo_root = isolated_env / "repo"
    repo_root.mkdir()
    known_hash = _make_hash("AC-GEN-018 known bundle")

    bundle, result, calls = _run(repo_root, known_hash)

    assert result is not None
    assert _field(result, "model_call_error") is None, _field(result, "model_call_error")
    assert _field(result, "refused") is None, _field(result, "refused")
    files = _field(result, "files")
    assert files, "expected a successful generation with non-empty files"
    assert calls, "the injected mock model was never called"

    got = _field(result, "spec_bundle_hash")
    assert isinstance(got, str)
    assert got == bundle.spec_bundle_hash
    assert got == known_hash


def test_spec_bundle_hash_tracks_each_distinct_bundle(isolated_env):
    hash_a = _make_hash("AC-GEN-018 bundle A")
    hash_b = _make_hash("AC-GEN-018 bundle B")
    assert hash_a != hash_b

    repo_a = isolated_env / "repo_a"
    repo_a.mkdir()
    repo_b = isolated_env / "repo_b"
    repo_b.mkdir()

    bundle_a, result_a, _ = _run(repo_a, hash_a)
    bundle_b, result_b, _ = _run(repo_b, hash_b, ["R-FOO-001"])

    assert _field(result_a, "files"), "bundle A generation did not succeed"
    assert _field(result_b, "files"), "bundle B generation did not succeed"
    assert _field(result_a, "spec_bundle_hash") == bundle_a.spec_bundle_hash == hash_a
    assert _field(result_b, "spec_bundle_hash") == bundle_b.spec_bundle_hash == hash_b


def test_spec_bundle_hash_echoed_on_repeat_call(isolated_env):
    repo_root = isolated_env / "repo"
    repo_root.mkdir()
    known_hash = _make_hash("AC-GEN-018 repeat")

    bundle, first, _ = _run(repo_root, known_hash)
    _, second, _ = _run(repo_root, known_hash)

    assert _field(first, "files"), "first generation did not succeed"
    assert _field(first, "spec_bundle_hash") == bundle.spec_bundle_hash
    assert _field(second, "spec_bundle_hash") == bundle.spec_bundle_hash