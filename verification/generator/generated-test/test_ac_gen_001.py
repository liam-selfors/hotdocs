# hotdocs-criterion: sha256:df8961ca05e47121c532faf44603e546c6160c91d609167f635632881c1a5342
import generator

import dataclasses
import re
from pathlib import Path

import pytest


PYTHON_ADAPTER = (
    "from pathlib import Path\n"
    "\n"
    "KIND = 'python'\n"
    "\n"
    "\n"
    "def layout_errors(code_dir):\n"
    "    return ['bad.py:1: SyntaxError: x'] if (Path(code_dir) / 'bad.py').exists() else []\n"
    "\n"
    "\n"
    "def provision(repo_root):\n"
    "    return {'ok': True, 'reason': '', 'versions': {'python': '3.12'}, "
    "'lockfile_sha256': None, 'interpreter': '/fake/python'}\n"
)

COMPONENT_MD = (
    "---\n"
    "id: comp-foo\n"
    "title: Foo\n"
    "status: draft\n"
    "owners: [pipeline-team]\n"
    "depends_on: [comp-bar]\n"
    "sealed: false\n"
    "---\n"
    "\n"
    "# Foo\n"
)


@dataclasses.dataclass
class FakeSpecBundle:
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

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default

    def keys(self):
        return [f.name for f in dataclasses.fields(self)]


def section(prompt, heading):
    lines = prompt.split("\n")
    start = lines.index(heading) + 1
    end = next((i for i in range(start, len(lines)) if lines[i].startswith("## ")), len(lines))
    return "\n".join(lines[start:end]).rstrip("\n")


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def test_ac_gen_001_cold_prompt_sections(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    repo_root = tmp_path / "repo"
    adapter_dir = repo_root / "gen" / "kind-python"
    adapter_dir.mkdir(parents=True)
    (adapter_dir / "kind_python.py").write_text(PYTHON_ADAPTER, encoding="utf-8")
    comp_dir = repo_root / "specs" / "components" / "foo"
    comp_dir.mkdir(parents=True)
    (comp_dir / "component.md").write_text(COMPONENT_MD, encoding="utf-8")

    bundle = FakeSpecBundle(
        component_id="comp-foo",
        spec_bundle_hash="sha256:" + "a" * 64,
        spec="SPEC-MARK",
        interface="IFACE-MARK",
        constraints="CONS-MARK",
        dependency_interfaces={"comp-bar": "DI-MARK"},
        dependency_context={"comp-bar": "DC-MARK"},
        dependency_usage={"comp-bar": ""},
        vars={"VAR-X": "VAR-MARK"},
        glossary="GLOSS-MARK",
        hint_code=None,
    )

    recorded = []

    def mock_backend(prompt, model, **params):
        recorded.append(prompt)
        nonce = re.search(r"-----BEGIN FILE ([0-9a-f]{32}):", prompt).group(1)
        reply = (
            "-----BEGIN FILE " + nonce + ": foo.py-----\n"
            "X = 1\n"
            "-----END FILE " + nonce + "-----\n"
            "-----END REPLY " + nonce + "-----\n"
        )
        return {"text": reply, "model": model, "backend": "mock", "model_call_error": None}

    result = generator.generate(
        bundle, "mock-model", None, repo_root=repo_root, llm_backend=mock_backend
    )

    assert field(result, "refused") is None
    assert len(recorded) == 1
    prompt = recorded[0]

    assert section(prompt, "## SPEC") == "SPEC-MARK"
    assert section(prompt, "## INTERFACE") == "IFACE-MARK"
    assert section(prompt, "## CONSTRAINTS") == "CONS-MARK"
    assert section(prompt, "## DEPENDENCY INTERFACES") == "### comp-bar\nDI-MARK"
    assert section(prompt, "## DEPENDENCY CONTEXT") == "### comp-bar\nDC-MARK"
    assert section(prompt, "## VARS") == "### VAR-X\nVAR-MARK"
    assert section(prompt, "## GLOSSARY") == "GLOSS-MARK"

    lines = prompt.split("\n")
    assert "## DEPENDENCY USAGE" not in lines
    assert "## HINT_CODE" not in lines
    assert "## RETRY_FEEDBACK" not in lines