# hotdocs-criterion: sha256:142a24f6b07b727caa6d8c04b80521c2e1c28a1e5a6d0126b7ff5e4415dcb342
import hashlib
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
    "## Layout\nx\n\n"
    "## Environment\nx\n\n"
    "## Surface\nx\n\n"
    "## Running criteria\nx\n\n"
    "## Strength check\nx\n\n"
    "## Test author guidance\nx\n\n"
    "## Generator guidance\nx\n"
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


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _plant_repo(repo_root):
    _write(repo_root / "specs" / "components" / "widget-maker" / "component.md", COMPONENT_MD)
    _write(repo_root / "specs" / "architecture" / "asset-kind-fake.md", FAKE_DEFINITION)
    _write(repo_root / "gen" / "kind-fake" / "kind_fake.py", FAKE_ADAPTER)
    _write(repo_root / "gen" / "kind-python" / "kind_python.py", PYTHON_ADAPTER)


def _bundle():
    spec_text = "# Widget Maker\n\nThe component makes widgets."
    return {
        "component_id": "comp-widget-maker",
        "spec_bundle_hash": "sha256:" + hashlib.sha256(b"ac-gen-025 bundle").hexdigest(),
        "spec": spec_text,
        "interface": "# Library\n\nmake() -> str",
        "constraints": "No constraints.",
        "dependency_interfaces": {},
        "dependency_context": {},
        "dependency_usage": {},
        "vars": {},
        "glossary": "",
        "hint_code": None,
    }


def test_ac_gen_025_prompt_names_module_and_asset_before_spec(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    monkeypatch.chdir(tmp_path)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _plant_repo(repo_root)

    prompts = []

    def mock_backend(prompt, model, **params):
        prompts.append(prompt)
        nonce = re.search(r"-----BEGIN FILE ([0-9a-f]{32}):", prompt).group(1)
        reply = (
            "-----BEGIN FILE " + nonce + ": widget_maker.py-----\n"
            "VALUE = 1\n"
            "-----END FILE " + nonce + "-----\n"
            "-----BEGIN FILE " + nonce + ": static/app.txt-----\n"
            "ok\n"
            "-----END FILE " + nonce + "-----\n"
            "-----END REPLY " + nonce + "-----\n"
        )
        return {"text": reply, "model": model, "backend": "mock", "model_call_error": None}

    result = generator.generate(
        _bundle(), "claude-sonnet-5", repo_root=repo_root, llm_backend=mock_backend
    )

    assert field(result, "refused") is None
    assert len(prompts) >= 1, "the mock model was never called"

    prompt = prompts[0]
    lines = prompt.split("\n")
    assert "## SPEC" in lines, "prompt has no '## SPEC' line"
    spec_index = lines.index("## SPEC")
    preamble = "\n".join(lines[:spec_index])

    assert "widget_maker.py" in preamble
    assert "static/app.txt" in preamble