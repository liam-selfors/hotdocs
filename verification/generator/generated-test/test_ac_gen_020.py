# hotdocs-criterion: sha256:661e9a182423bea16648086aeb39016e5c40c6090007be6f9b3b82fea63ed8a1
import re
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

COMPONENT_MD = (
    "---\n"
    "id: comp-widget-maker\n"
    "title: Widget Maker\n"
    "status: draft\n"
    "owners: [pipeline-team]\n"
    "depends_on: []\n"
    "sealed: false\n"
    "---\n"
    "\n"
    "# Widget Maker\n"
)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _plant(repo_root):
    comp_dir = repo_root / "specs" / "components" / "widget-maker"
    comp_dir.mkdir(parents=True)
    (comp_dir / "component.md").write_text(COMPONENT_MD, encoding="utf-8")
    adapter_dir = repo_root / "gen" / "kind-python"
    adapter_dir.mkdir(parents=True)
    (adapter_dir / "kind_python.py").write_text(PYTHON_ADAPTER, encoding="utf-8")


def _bundle():
    # Bundle text deliberately avoids the words the instruction under test uses,
    # so any match in the prompt must come from the generator's own instructions.
    return {
        "component_id": "comp-widget-maker",
        "spec_bundle_hash": "sha256:" + "ab" * 32,
        "spec": "Widget Maker makes widgets.",
        "interface": "make_widget(name: str) -> str",
        "constraints": "Be quick.",
        "dependency_interfaces": {},
        "dependency_context": {},
        "dependency_usage": {},
        "vars": {},
        "glossary": "Widget: a thing.",
        "hint_code": None,
    }


def test_ac_gen_020_prompt_instructs_dual_access_for_dependency_values(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _plant(repo_root)

    sent = []

    def mock_backend(prompt, model, **params):
        sent.append(prompt)
        nonce = re.search(r"-----BEGIN FILE ([0-9a-f]{32}):", prompt).group(1)
        reply = (
            "-----BEGIN FILE " + nonce + ": widget_maker.py-----\n"
            "def make_widget(name):\n"
            "    return name\n"
            "-----END FILE " + nonce + "-----\n"
            "-----END REPLY " + nonce + "-----\n"
        )
        return {
            "text": reply,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    bundle = _bundle()
    generator.generate(bundle, "mock-model", repo_root=repo_root, llm_backend=mock_backend)

    assert sent, "the mock model was never called"
    prompt = sent[0]
    lowered = prompt.lower()

    for value in bundle.values():
        if isinstance(value, str):
            for word in ("attribute", "top-level", "top level", "dict"):
                assert word not in value.lower()

    assert "dependency" in lowered or "dependencies" in lowered
    assert "attribute" in lowered or "getattr" in lowered
    assert "dict" in lowered
    assert "top-level" in lowered or "top level" in lowered
    assert "return" in lowered