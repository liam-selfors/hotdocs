"""AC-GEN-003 (covers R-GEN-003).

Given any SpecBundle
When generate is called
Then the resulting GenerationResult's prompt_version matches the frozen
  template's declared version.
"""

import hashlib
import json
import re
from dataclasses import dataclass, field, fields
from pathlib import Path

import pytest

import generator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SENTINEL = object()


def _field(value, name, default=None):
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


@dataclass
class FakeSpecBundle:
    """Duck-typed stand-in matching spec-bundle-assembler's documented
    `SpecBundle` shape: a dataclass with these fields in this order that
    also reads as a read-only mapping."""

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
    hint_code: dict = None

    def _names(self):
        return [f.name for f in fields(self)]

    def __getitem__(self, key):
        if key not in self._names():
            raise KeyError(key)
        return getattr(self, key)

    def get(self, key, default=None):
        if key not in self._names():
            return default
        return getattr(self, key)

    def __contains__(self, key):
        return key in self._names()

    def __iter__(self):
        return iter(self._names())

    def __len__(self):
        return len(self._names())

    def keys(self):
        return list(self._names())

    def items(self):
        return [(k, getattr(self, k)) for k in self._names()]

    def values(self):
        return [getattr(self, k) for k in self._names()]


def _make_bundle(component_id, spec, interface, constraints, **extra):
    material = json.dumps(
        {
            "component_id": component_id,
            "spec": spec,
            "interface": interface,
            "constraints": constraints,
            "extra": {k: extra[k] for k in sorted(extra)},
        },
        sort_keys=True,
        default=str,
    ).encode("utf-8")
    bundle_hash = "sha256:" + hashlib.sha256(material).hexdigest()
    return FakeSpecBundle(
        component_id=component_id,
        spec_bundle_hash=bundle_hash,
        spec=spec,
        interface=interface,
        constraints=constraints,
        **extra,
    )


def _write_component_md(repo_root: Path, slug: str, component_id: str, title: str):
    comp_dir = repo_root / "specs" / "components" / slug
    comp_dir.mkdir(parents=True, exist_ok=True)
    content = (
        "---\n"
        f"id: {component_id}\n"
        f"title: {title}\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "sealed: false\n"
        "depends_on: []\n"
        "---\n"
        "\n"
        f"# {title}\n"
        "\n"
        "## Purpose\n"
        "\n"
        f"{title} is a test component.\n"
    )
    (comp_dir / "component.md").write_text(content, encoding="utf-8")


def _extract_nonce(prompt: str):
    m = re.search(r"BEGIN FILE ([0-9a-f]{32})", prompt)
    if m:
        return m.group(1)
    m = re.search(r"(?<![0-9a-f])([0-9a-f]{32})(?![0-9a-f])", prompt)
    if m:
        return m.group(1)
    return None


def _make_success_backend(log_path: Path, files: dict):
    def backend(prompt, model, **params):
        nonce = _extract_nonce(prompt)
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"call": "success", "nonce": nonce, "model": model}) + "\n")
        blocks = []
        for path, content in files.items():
            body = content if content.endswith("\n") else content + "\n"
            blocks.append(
                f"-----BEGIN FILE {nonce}: {path}-----\n"
                f"{body}"
                f"-----END FILE {nonce}-----\n"
            )
        text = "Here are the files.\n" + "".join(blocks)
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    return backend


def _make_failing_backend(log_path: Path):
    def backend(prompt, model, **params):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"call": "failure", "model": model}) + "\n")
        raise ConnectionError("simulated backend failure")

    return backend


@pytest.fixture
def repo_root(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "specs").mkdir()
    (root / "specs" / "glossary.md").write_text(
        "# Glossary\n\n- **Foo** — a test term.\n", encoding="utf-8"
    )
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    monkeypatch.chdir(root)
    return root


# ---------------------------------------------------------------------------
# Bundle variety ("any SpecBundle")
# ---------------------------------------------------------------------------

_BUNDLE_CASES = [
    (
        "foo",
        "comp-foo",
        "Foo",
        dict(
            spec="# Foo\n\n## Purpose\n\nFoo doubles a number.\n\n# R-FOO-001\n\n"
            "**R-FOO-001** — `foo(x)` MUST return `2 * x`.",
            interface="# Library\n\n```\nfoo(x: int) -> int\n```",
            constraints="# Constraints\n\nNone.",
        ),
        {"foo.py": "def foo(x):\n    return 2 * x\n"},
    ),
    (
        "bar-baz",
        "comp-bar-baz",
        "Bar Baz",
        dict(
            spec="# Bar Baz\n\n## Purpose\n\nBar Baz greets.\n\n# R-BARBAZ-001\n\n"
            "**R-BARBAZ-001** — `greet(name)` MUST return `'hi ' + name`.",
            interface="# Library\n\n```\ngreet(name: str) -> str\n```",
            constraints="# Constraints\n\nNo network access.",
            dependency_interfaces={"comp-foo": "# Library\n\n```\nfoo(x: int) -> int\n```"},
            dependency_context={"comp-foo": "Foo doubles a number."},
            dependency_usage={"comp-foo": ""},
            vars={"VAR-BAR-URL": "The bar URL."},
            glossary="# Glossary\n\n- **Foo** — a test term.",
        ),
        {
            "bar_baz.py": "def greet(name):\n    return 'hi ' + name\n",
            "helpers/util.py": "X = 1\n",
        },
    ),
]


def _assert_prompt_version(result):
    assert result is not None
    pv = _field(result, "prompt_version", _SENTINEL)
    assert pv is not _SENTINEL, "GenerationResult has no prompt_version field"
    assert isinstance(pv, str) and pv, f"prompt_version must be a non-empty string, got {pv!r}"
    assert pv == generator.PROMPT_VERSION, (
        f"prompt_version {pv!r} != frozen template version {generator.PROMPT_VERSION!r}"
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_prompt_version_constant_is_declared_and_frozen():
    pv = getattr(generator, "PROMPT_VERSION", None)
    assert isinstance(pv, str) and pv
    assert pv == "v10"


@pytest.mark.parametrize("retry_feedback", [None, ["R-FOO-001"]])
@pytest.mark.parametrize(
    "slug,component_id,title,bundle_kwargs,files",
    _BUNDLE_CASES,
    ids=[c[1] for c in _BUNDLE_CASES],
)
def test_generate_result_prompt_version_matches_frozen_template(
    repo_root, tmp_path, slug, component_id, title, bundle_kwargs, files, retry_feedback
):
    _write_component_md(repo_root, slug, component_id, title)
    bundle = _make_bundle(component_id, **bundle_kwargs)
    log_path = tmp_path / "backend_calls.log"
    backend = _make_success_backend(log_path, files)

    result = generator.generate(
        bundle,
        "claude-sonnet-5",
        retry_feedback,
        repo_root=repo_root,
        llm_backend=backend,
    )

    _assert_prompt_version(result)
    assert _field(result, "component_id") == component_id

    # A second identical call (possibly served from cache) must carry the
    # same frozen template version too.
    second = generator.generate(
        bundle,
        "claude-sonnet-5",
        retry_feedback,
        repo_root=repo_root,
        llm_backend=backend,
    )
    _assert_prompt_version(second)
    assert _field(second, "prompt_version") == _field(result, "prompt_version")


def test_generate_prompt_version_on_model_call_error(repo_root, tmp_path):
    slug, component_id, title, bundle_kwargs, _files = _BUNDLE_CASES[0]
    _write_component_md(repo_root, slug, component_id, title)
    bundle = _make_bundle(component_id, **bundle_kwargs)
    log_path = tmp_path / "backend_failures.log"

    result = generator.generate(
        bundle,
        "claude-sonnet-5",
        None,
        repo_root=repo_root,
        llm_backend=_make_failing_backend(log_path),
    )

    _assert_prompt_version(result)