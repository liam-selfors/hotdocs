# hotdocs-criterion: sha256:c7c1cbd1bfafd810e7c71f1bdfa14117b9bd2da1101f75dedb8a2e282861244d
import dataclasses
import re
from pathlib import Path

import pytest

import generator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


@dataclasses.dataclass
class Bundle:
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
        if key not in self.keys():
            raise KeyError(key)
        return getattr(self, key)

    def get(self, key, default=None):
        if key in self.keys():
            return getattr(self, key)
        return default

    def keys(self):
        return [f.name for f in dataclasses.fields(self)]

    def __iter__(self):
        return iter(self.keys())

    def __contains__(self, key):
        return key in self.keys()

    def __len__(self):
        return len(self.keys())


def make_bundle(hash_char):
    return Bundle(
        component_id="comp-foo",
        spec_bundle_hash="sha256:" + hash_char * 64,
        spec="# Foo\n\n## Purpose\n\nFoo doubles a number.\n\n# R-FOO-001\n\n**R-FOO-001** \u2014 `foo(x)` MUST return `2 * x`.",
        interface="# Library\n\n```\nfoo(x: int) -> int\n```",
        constraints="# Constraints\n\nNone.",
        dependency_interfaces={},
        dependency_context={},
        dependency_usage={},
        vars={},
        glossary="# Glossary\n\n- **Foo** \u2014 a test term.",
        hint_code=None,
    )


def write_component(repo_root):
    comp_dir = repo_root / "specs" / "components" / "foo"
    comp_dir.mkdir(parents=True, exist_ok=True)
    text = (
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
        "Foo doubles a number.\n"
    )
    (comp_dir / "component.md").write_text(text, encoding="utf-8")


def make_backend(recorded):
    def backend(prompt, model, **params):
        recorded.append(prompt)
        m = re.search(r"-----BEGIN FILE ([0-9a-f]{32})", prompt)
        assert m is not None, "prompt does not state a nonce in the reply-format markers"
        nonce = m.group(1)
        text = (
            "-----BEGIN FILE " + nonce + ": foo.py-----\n"
            + "def foo(x):\n"
            + "    return 2 * x\n"
            + "-----END FILE " + nonce + "-----\n"
        )
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    return backend


@pytest.fixture(autouse=True)
def _no_remote_cache(monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)


def test_prompt_instructs_dynamic_dependency_loads_resolve_from_repo_root(tmp_path):
    repo_root = tmp_path
    write_component(repo_root)
    recorded = []
    bundle = make_bundle("a")

    result = generator.generate(
        bundle, "claude-sonnet-5", repo_root=repo_root, llm_backend=make_backend(recorded)
    )

    assert recorded, "mock model was never called"
    prompt = recorded[0]
    lowered = prompt.lower()

    # The instruction must hold regardless of depends_on: this bundle has no
    # dependencies at all, so the instruction must come from the fixed prompt.
    assert "repo_root" in prompt
    assert "import" in lowered
    assert "sys.modules" in prompt
    assert "__file__" in prompt
    assert "gen/" in prompt
    assert "tool" in lowered

    assert field(result, "refused") is None
    assert field(result, "model_call_error") is None


def test_generate_completes_without_gen_dir_in_repo_root(tmp_path):
    repo_root = tmp_path
    write_component(repo_root)
    assert not (repo_root / "gen").exists()
    recorded = []
    bundle = make_bundle("b")

    result = generator.generate(
        bundle, "claude-sonnet-5", repo_root=repo_root, llm_backend=make_backend(recorded)
    )

    assert len(recorded) >= 1
    assert field(result, "refused") is None
    assert field(result, "model_call_error") is None
    files = field(result, "files")
    assert files, "expected non-empty files"
    assert "foo.py" in files
    assert "return 2 * x" in files["foo.py"]
    assert field(result, "component_id") == "comp-foo"
    assert field(result, "spec_bundle_hash") == bundle.spec_bundle_hash