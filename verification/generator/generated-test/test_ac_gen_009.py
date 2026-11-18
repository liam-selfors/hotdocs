# hotdocs-criterion: sha256:c7142ff1f230f6b1088fe2f13ca9e8de65faa0e4d6d2f626c7fc89ad2cc2be4c
import json
import re
from pathlib import Path

import pytest

import generator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


class Bundle:
    _FIELDS = (
        "component_id",
        "spec_bundle_hash",
        "spec",
        "interface",
        "constraints",
        "dependency_interfaces",
        "dependency_context",
        "dependency_usage",
        "vars",
        "glossary",
        "hint_code",
    )

    def __init__(self, component_id, spec_bundle_hash):
        self.component_id = component_id
        self.spec_bundle_hash = spec_bundle_hash
        self.spec = "# Spec\n\nDoubles a number."
        self.interface = "# Library\n\n    foo(x: int) -> int"
        self.constraints = "# Constraints\n\nNone."
        self.dependency_interfaces = {}
        self.dependency_context = {}
        self.dependency_usage = {}
        self.vars = {}
        self.glossary = "# Glossary\n\n- **Foo** — a test term."
        self.hint_code = None

    def __getitem__(self, key):
        if key not in self._FIELDS:
            raise KeyError(key)
        return getattr(self, key)

    def get(self, key, default=None):
        if key in self._FIELDS:
            return getattr(self, key)
        return default

    def keys(self):
        return list(self._FIELDS)

    def __iter__(self):
        return iter(self._FIELDS)

    def __contains__(self, key):
        return key in self._FIELDS

    def __len__(self):
        return len(self._FIELDS)


def make_backend(log_path):
    def backend(prompt, model, **params):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write("called\n")
        m = re.search(r"-----BEGIN FILE ([0-9a-f]{32}):", prompt)
        nonce = m.group(1) if m else "0" * 32
        text = (
            "-----BEGIN FILE " + nonce + ": out.py-----\n"
            + "def foo(x):\n    return 2 * x\n"
            + "-----END FILE " + nonce + "-----\n"
            + "-----END REPLY " + nonce + "-----\n"
        )
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    return backend


def write_sealed_component(repo_root):
    comp_dir = repo_root / "specs" / "components" / "foo"
    comp_dir.mkdir(parents=True, exist_ok=True)
    (comp_dir / "component.md").write_text(
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
        encoding="utf-8",
    )
    legacy = repo_root / "legacy" / "foo"
    legacy.mkdir(parents=True, exist_ok=True)
    (legacy / "foo.py").write_text("def foo(x):\n    return 2 * x\n", encoding="utf-8")
    return "comp-foo", "foo"


def write_pinned_component(repo_root):
    comp_dir = repo_root / "specs" / "components" / "bar"
    comp_dir.mkdir(parents=True, exist_ok=True)
    (comp_dir / "component.md").write_text(
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
        encoding="utf-8",
    )
    gen_dir = repo_root / "gen" / "bar"
    gen_dir.mkdir(parents=True, exist_ok=True)
    (gen_dir / "bar.py").write_text("def bar(x):\n    return 2 * x\n", encoding="utf-8")
    (gen_dir / ".overrides.json").write_text(json.dumps(["bar.py"]), encoding="utf-8")
    return "comp-bar", "bar"


@pytest.mark.parametrize(
    "builder, expected_reason",
    [
        (write_sealed_component, "sealed-component"),
        (write_pinned_component, "pinned-override"),
    ],
)
def test_exempt_component_refused_before_model_call(
    tmp_path, monkeypatch, builder, expected_reason
):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)

    component_id, slug = builder(repo_root)
    gen_dir = repo_root / "gen" / slug
    before = {}
    if gen_dir.is_dir():
        for p in gen_dir.rglob("*"):
            if p.is_file():
                before[str(p.relative_to(gen_dir))] = p.read_bytes()

    log_path = tmp_path / "model_calls.log"
    backend = make_backend(log_path)

    bundle = Bundle(component_id, "sha256:" + "a" * 64)

    result = generator.generate(
        bundle,
        "mock-model",
        None,
        repo_root=repo_root,
        llm_backend=backend,
    )

    # The mock model is never called.
    assert not log_path.exists() or log_path.read_text(encoding="utf-8") == ""

    # files empty, model_call_error null, refused names the exemption.
    files = field(result, "files")
    assert not files
    assert files == {}
    assert field(result, "model_call_error") is None
    refused = field(result, "refused")
    assert isinstance(refused, str)
    assert refused == expected_reason
    assert field(result, "cache_hit") is False

    # Nothing in the declared hands-off paths was clobbered.
    after = {}
    if gen_dir.is_dir():
        for p in gen_dir.rglob("*"):
            if p.is_file():
                after[str(p.relative_to(gen_dir))] = p.read_bytes()
    assert after == before
    if expected_reason == "sealed-component":
        assert (repo_root / "legacy" / "foo" / "foo.py").read_text(
            encoding="utf-8"
        ) == "def foo(x):\n    return 2 * x\n"