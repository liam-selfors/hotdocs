# hotdocs-criterion: sha256:856eef1f12da722c6a8899f9c7089ca900c95ab0b942fd2d5100fa431e62bfda
import re
from pathlib import Path

import generator


COMPONENT_MD = (
    "---\n"
    "id: comp-widget-maker\n"
    "title: Widget Maker\n"
    "status: draft\n"
    "owners: [pipeline-team]\n"
    "depends_on: []\n"
    "sealed: false\n"
    "assets: [fake:static/app.txt]\n"
    "---\n"
    "\n"
    "# Widget Maker\n"
)

FAKE_DEFINITION = (
    "# Fake\n"
    "\n"
    "## Layout\n"
    "x\n"
    "\n"
    "## Environment\n"
    "x\n"
    "\n"
    "## Surface\n"
    "x\n"
    "\n"
    "## Running criteria\n"
    "x\n"
    "\n"
    "## Strength check\n"
    "x\n"
    "\n"
    "## Test author guidance\n"
    "x\n"
    "\n"
    "## Generator guidance\n"
    "x\n"
)

FAKE_ADAPTER = (
    "from pathlib import Path\n"
    "\n"
    "KIND = \"fake\"\n"
    "\n"
    "\n"
    "def layout_errors(asset_file):\n"
    "    return [\"bad\"] if \"bad\" in Path(asset_file).read_text(encoding=\"utf-8\") else []\n"
    "\n"
    "\n"
    "def provision(repo_root):\n"
    "    if (Path(repo_root) / \"NO_ENV\").exists():\n"
    "        return {\"ok\": False, \"reason\": \"fake needs fakeprog >= 2\", \"versions\": {}, \"lockfile_sha256\": None}\n"
    "    return {\"ok\": True, \"reason\": \"\", \"versions\": {\"fakeprog\": \"2.0.0\"}, \"lockfile_sha256\": None}\n"
)

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


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _plant(repo_root):
    _write(repo_root / "specs" / "components" / "widget-maker" / "component.md", COMPONENT_MD)
    _write(repo_root / "specs" / "architecture" / "asset-kind-fake.md", FAKE_DEFINITION)
    _write(repo_root / "gen" / "kind-fake" / "kind_fake.py", FAKE_ADAPTER)
    _write(repo_root / "gen" / "kind-python" / "kind_python.py", PYTHON_ADAPTER)


def _bundle():
    return {
        "component_id": "comp-widget-maker",
        "spec_bundle_hash": "sha256:" + "a" * 64,
        "spec": "Widget Maker makes widgets.",
        "interface": "make() -> int",
        "constraints": "None.",
        "dependency_interfaces": {},
        "dependency_context": {},
        "dependency_usage": {},
        "vars": {},
        "glossary": "",
        "hint_code": None,
    }


def test_prompt_names_module_and_asset_before_spec(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _plant(repo_root)

    prompts = []

    def mock_backend(prompt, model, **params):
        prompts.append(prompt)
        nonce = re.search(r"-----BEGIN FILE ([0-9a-f]{32}):", prompt).group(1)
        reply = (
            "-----BEGIN FILE " + nonce + ": widget_maker.py-----\n"
            "def make():\n"
            "    return 1\n"
            "-----END FILE " + nonce + "-----\n"
            "-----BEGIN FILE " + nonce + ": static/app.txt-----\n"
            "ok\n"
            "-----END FILE " + nonce + "-----\n"
            "-----END REPLY " + nonce + "-----\n"
        )
        return {
            "text": reply,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    generator.generate(
        _bundle(),
        "claude-sonnet-5",
        repo_root=repo_root,
        llm_backend=mock_backend,
    )

    assert prompts, "mock model was never called"
    prompt = prompts[0]

    lines = prompt.split("\n")
    assert "## SPEC" in lines, "prompt has no '## SPEC' line"
    spec_index = lines.index("## SPEC")
    before = "\n".join(lines[:spec_index])

    assert "widget_maker.py" in before
    assert "static/app.txt" in before