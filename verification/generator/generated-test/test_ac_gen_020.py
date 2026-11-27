# hotdocs-criterion: sha256:d028382636441335e153911e6e851bac14640843c747052200dfb4a5399fa56d
"""AC-GEN-020: the prompt instructs dual dict-or-attribute access for every
value read from a dependency call, the dependency's own top-level return
value included (R-GEN-019)."""

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
    "    return {\"ok\": True, \"reason\": \"\", \"versions\": {\"python\": \"3.12\"}, \"lockfile_sha256\": None, \"interpreter\": \"/fake/python\"}\n"
)


@dataclass
class Bundle:
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
    spec_bundle_parts: dict = dc_field(default_factory=dict)

    def __getitem__(self, key):
        try:
            return getattr(self, key)
        except AttributeError:
            raise KeyError(key)

    def get(self, key, default=None):
        return getattr(self, key, default)

    def keys(self):
        return list(self.__dataclass_fields__)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _plant(repo_root):
    adapter = repo_root / "gen" / "kind-python" / "kind_python.py"
    adapter.parent.mkdir(parents=True, exist_ok=True)
    adapter.write_text(PYTHON_ADAPTER, encoding="utf-8")
    comp = repo_root / "specs" / "components" / "widget-maker" / "component.md"
    comp.parent.mkdir(parents=True, exist_ok=True)
    comp.write_text(
        "---\n"
        "id: comp-widget-maker\n"
        "title: Widget Maker\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "depends_on: []\n"
        "sealed: false\n"
        "---\n"
        "\n"
        "# Widget Maker\n",
        encoding="utf-8",
    )


def test_ac_gen_020_prompt_requires_dual_access_for_dependency_values(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _plant(repo_root)

    # Bundle text deliberately avoids the words the instruction is checked by.
    bundle = Bundle(
        component_id="comp-widget-maker",
        spec_bundle_hash="sha256:" + "a" * 64,
        spec="Widget maker makes widgets.",
        interface="make_widget(name) -> str",
        constraints="Be quick.",
        glossary="Widget: a small thing.",
        hint_code=None,
    )

    sent = []

    def mock_backend(prompt, model, **params):
        sent.append(prompt)
        nonce = re.search(r"-----BEGIN FILE ([0-9a-f]{32}):", prompt).group(1)
        text = (
            "-----BEGIN FILE " + nonce + ": widget_maker.py-----\n"
            "X = 1\n"
            "-----END FILE " + nonce + "-----\n"
            "-----END REPLY " + nonce + "-----\n"
        )
        return {"text": text, "model": model, "backend": "mock", "model_call_error": None}

    result = generator.generate(
        bundle, "mock-model", repo_root=repo_root, llm_backend=mock_backend
    )

    assert len(sent) >= 1, "the mock model was never called"
    assert field(result, "cache_hit") is False
    prompt = sent[-1]

    # Paragraphs that speak of both dicts and attributes form the instruction.
    paragraphs = re.split(r"\n\s*\n", prompt)
    relevant = [
        p for p in paragraphs
        if "attribute" in p.lower() and "dict" in p.lower()
    ]
    assert relevant, "prompt never instructs dict-or-attribute access"
    text = "\n".join(relevant).lower()

    assert "dependenc" in text, (
        "the dual-access instruction does not concern dependency values: " + text
    )
    assert any(
        term in text
        for term in ("top-level", "top level", "return value", "returned value", "own return", "returns")
    ), "the instruction does not cover the dependency's own top-level return value: " + text
    assert any(
        term in text for term in ("never", "not ", "bare", "alone", "only")
    ), "the instruction does not forbid a bare attribute access: " + text