# hotdocs-criterion: sha256:ea50adf41505c9f22d32def788f48535b67c1ef7ddb95858f8ff94e376f70517
import re
from dataclasses import dataclass, field as dc_field
from pathlib import Path

import generator


PYTHON_ADAPTER = (
    "from pathlib import Path\n"
    "\n"
    "KIND = \"python\"\n"
    "\n"
    "\n"
    "def layout_errors(code_dir):\n"
    "    return [\"bad.py:1: SyntaxError: x\"] if (Path(code_dir) / \"bad.py\").exists() else []\n"
    "\n"
    "\n"
    "def provision(repo_root):\n"
    "    return {\"ok\": True, \"reason\": \"\", \"versions\": {\"python\": \"3.12\"}, "
    "\"lockfile_sha256\": None, \"interpreter\": \"/fake/python\"}\n"
)


@dataclass
class FakeSpecBundle:
    component_id: str
    spec_bundle_hash: str
    spec: str
    interface: str
    constraints: str
    dependency_interfaces: dict = dc_field(default_factory=dict)
    dependency_context: dict = dc_field(default_factory=dict)
    dependency_usage: dict = dc_field(default_factory=dict)
    vars: dict = dc_field(default_factory=dict)
    glossary: str = ""
    hint_code: object = None

    def __getitem__(self, key):
        return getattr(self, key)

    def get(self, key, default=None):
        return getattr(self, key, default)

    def keys(self):
        return list(self.__dataclass_fields__.keys())


def section(prompt, heading):
    lines = prompt.split("\n")
    start = lines.index(heading) + 1
    end = next((i for i in range(start, len(lines)) if lines[i].startswith("## ")), len(lines))
    return "\n".join(lines[start:end]).rstrip("\n")


def test_ac_gen_001_cold_prompt_sections(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)

    adapter_dir = repo_root / "gen" / "kind-python"
    adapter_dir.mkdir(parents=True)
    (adapter_dir / "kind_python.py").write_text(PYTHON_ADAPTER, encoding="utf-8")

    bundle = FakeSpecBundle(
        component_id="comp-foo",
        spec_bundle_hash="sha256:" + "a1" * 32,
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
        text = (
            "-----BEGIN FILE " + nonce + ": foo.py-----\n"
            "x = 1\n"
            "-----END FILE " + nonce + "-----\n"
            "-----END REPLY " + nonce + "-----\n"
        )
        return {"text": text, "model": model, "backend": "mock", "model_call_error": None}

    generator.generate(bundle, "mock-model", repo_root=repo_root, llm_backend=mock_backend)

    assert len(recorded) == 1
    prompt = recorded[0]

    assert section(prompt, "## SPEC") == "SPEC-MARK"
    assert section(prompt, "## DEPENDENCY CONTEXT") == "### comp-bar\nDC-MARK"

    assert section(prompt, "## INTERFACE") == "IFACE-MARK"
    assert section(prompt, "## CONSTRAINTS") == "CONS-MARK"
    assert section(prompt, "## DEPENDENCY INTERFACES") == "### comp-bar\nDI-MARK"
    assert section(prompt, "## VARS") == "### VAR-X\nVAR-MARK"
    assert section(prompt, "## GLOSSARY") == "GLOSS-MARK"

    lines = prompt.split("\n")
    assert "## DEPENDENCY USAGE" not in lines
    assert "## HINT_CODE" not in lines
    assert "## RETRY_FEEDBACK" not in lines