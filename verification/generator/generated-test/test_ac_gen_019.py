# hotdocs-criterion: sha256:08155118fa004941690baf6040bd262d11d825e4ed37f426acb382c9bdf3792c
import hashlib
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


def make_bundle(tag):
    return {
        "component_id": "comp-widget-maker",
        "spec_bundle_hash": "sha256:" + hashlib.sha256(tag.encode("utf-8")).hexdigest(),
        "spec": "Widget maker spec. It makes widgets.",
        "interface": "make_widget() -> int",
        "constraints": "Keep it small.",
        "dependency_interfaces": {},
        "dependency_context": {},
        "dependency_usage": {},
        "vars": {},
        "glossary": "Widget: a thing.",
        "hint_code": None,
    }


def make_backend(calls):
    def backend(prompt, model, **params):
        calls.append(prompt)
        nonce = re.search(r"-----BEGIN FILE ([0-9a-f]{32}):", prompt).group(1)
        text = (
            "-----BEGIN FILE " + nonce + ": widget_maker.py-----\n"
            "def make_widget():\n"
            "    return 1\n"
            "-----END FILE " + nonce + "-----\n"
            "-----END REPLY " + nonce + "-----\n"
        )
        return {"text": text, "model": model, "backend": "mock", "model_call_error": None}

    return backend


def plant_python_adapter(repo_root):
    adapter = repo_root / "gen" / "kind-python" / "kind_python.py"
    adapter.parent.mkdir(parents=True, exist_ok=True)
    adapter.write_text(PYTHON_ADAPTER, encoding="utf-8")


def plant_component(repo_root):
    comp = repo_root / "specs" / "components" / "widget-maker" / "component.md"
    comp.parent.mkdir(parents=True, exist_ok=True)
    comp.write_text(COMPONENT_MD, encoding="utf-8")


def test_prompt_instructs_dynamic_loads_resolve_from_repo_root(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    plant_python_adapter(repo_root)
    plant_component(repo_root)

    calls = []
    generator.generate(
        make_bundle("ac-gen-019-a"),
        "mock-model",
        repo_root=repo_root,
        llm_backend=make_backend(calls),
    )

    assert len(calls) >= 1
    prompt = calls[0]
    low = prompt.lower()
    assert "repo_root" in prompt
    assert "sys.modules" in prompt
    assert "__file__" in prompt
    assert "import" in low
    assert any(s in low for s in ("tool root", "tool's root", "tool_root", "tool's own")), prompt


def test_generate_completes_without_gen_dir_in_repo_root(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    plant_component(repo_root)
    assert not (repo_root / "gen").exists()

    calls = []
    result = generator.generate(
        make_bundle("ac-gen-019-b"),
        "mock-model",
        repo_root=repo_root,
        llm_backend=make_backend(calls),
    )

    assert result is not None
    assert field(result, "component_id") == "comp-widget-maker"
    assert field(result, "prompt_version") == generator.PROMPT_VERSION
    assert len(calls) == 1
    err = field(result, "model_call_error")
    assert err is None or field(err, "category") != "environment"