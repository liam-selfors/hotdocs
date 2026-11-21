# hotdocs-criterion: sha256:e72f0eabeba9a2bdef90727187a5541a18a06627096290ff70a4c73e527cd9ed
import re
import uuid
from pathlib import Path

import generator


FAKE_PYTHON_ADAPTER = (
    "from pathlib import Path\n"
    "\n"
    "KIND = " + repr("python") + "\n"
    "\n"
    "\n"
    "def layout_errors(code_dir):\n"
    "    return [" + repr("bad.py:1: SyntaxError: x") + "] if (Path(code_dir) / " + repr("bad.py") + ").exists() else []\n"
    "\n"
    "\n"
    "def provision(repo_root):\n"
    "    return {" + repr("ok") + ": True, " + repr("reason") + ": " + repr("") + ", "
    + repr("versions") + ": {" + repr("python") + ": " + repr("3.12") + "}, "
    + repr("lockfile_sha256") + ": None, " + repr("interpreter") + ": " + repr("/fake/python") + "}\n"
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


def _plant_repo(repo_root):
    adapter_dir = repo_root / "gen" / "kind-python"
    adapter_dir.mkdir(parents=True)
    (adapter_dir / "kind_python.py").write_text(FAKE_PYTHON_ADAPTER, encoding="utf-8")
    comp_dir = repo_root / "specs" / "components" / "widget-maker"
    comp_dir.mkdir(parents=True)
    (comp_dir / "component.md").write_text(COMPONENT_MD, encoding="utf-8")


def _bundle():
    return {
        "component_id": "comp-widget-maker",
        "spec_bundle_hash": "sha256:" + uuid.uuid4().hex + uuid.uuid4().hex,
        "spec": "# Widget Maker\n\nMakes widgets.",
        "interface": "make_widget() -> str",
        "constraints": "No network.",
        "dependency_interfaces": {},
        "dependency_context": {},
        "dependency_usage": {},
        "vars": {},
        "glossary": "",
        "hint_code": None,
    }


def test_ac_gen_022_prompt_says_nothing_more_and_mutation_testing(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _plant_repo(repo_root)

    prompts = []

    def mock_backend(prompt, model, **params):
        prompts.append(prompt)
        nonce = re.search(r"-----BEGIN FILE ([0-9a-f]{32}):", prompt).group(1)
        text = (
            "-----BEGIN FILE " + nonce + ": widget_maker.py-----\n"
            "def make_widget():\n"
            "    return 'widget'\n"
            "-----END FILE " + nonce + "-----\n"
            "-----END REPLY " + nonce + "-----\n"
        )
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    result = generator.generate(
        _bundle(),
        "mock:model-" + uuid.uuid4().hex,
        None,
        repo_root=repo_root,
        llm_backend=mock_backend,
    )

    assert field(result, "cache_hit") is False
    assert len(prompts) == 1
    prompt = prompts[0]
    assert "nothing more" in prompt
    assert "mutation testing" in prompt