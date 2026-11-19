# hotdocs-criterion: sha256:9bc81f66db10cce242e9e649532f7dfb7660c49e4d7317c63b79f523450df48c
import re
from pathlib import Path

import generator


PYTHON_ADAPTER = (
    "from pathlib import Path\n"
    "\n"
    "KIND = " + repr("python") + "\n"
    "\n"
    "\n"
    "def layout_errors(code_dir):\n"
    "    return [" + repr("bad.py:1: SyntaxError: x") + "] if (Path(code_dir) / "
    + repr("bad.py") + ").exists() else []\n"
    "\n"
    "\n"
    "def provision(repo_root):\n"
    "    return {" + repr("ok") + ": True, " + repr("reason") + ": " + repr("")
    + ", " + repr("versions") + ": {" + repr("python") + ": " + repr("3.12") + "}, "
    + repr("lockfile_sha256") + ": None, " + repr("interpreter") + ": "
    + repr("/fake/python") + "}\n"
)

COMPONENT_MD = (
    "---\n"
    "id: comp-widget-maker\n"
    "title: Widget Maker\n"
    "status: draft\n"
    "owners: [pipeline-team]\n"
    "depends_on: [comp-bar]\n"
    "sealed: false\n"
    "---\n"
    "\n"
    "# Widget Maker\n"
)

USAGE_TEXT = (
    "Module: bar_lib\n"
    "def bar_get(key: str) -> dict\n"
    "    USAGE_MARKER_7f3a: Return the entry stored under key."
)
INTERFACE_TEXT = "INTERFACE_MARKER_91c2: bar_get(key: str) -> Entry"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def section(prompt, heading):
    lines = prompt.split("\n")
    start = lines.index(heading) + 1
    end = next((i for i in range(start, len(lines)) if lines[i].startswith("## ")), len(lines))
    return "\n".join(lines[start:end]).rstrip("\n")


def test_dependency_usage_is_its_own_section(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    monkeypatch.chdir(tmp_path)
    repo_root = tmp_path / "repo"
    (repo_root / "gen" / "kind-python").mkdir(parents=True)
    (repo_root / "gen" / "kind-python" / "kind_python.py").write_text(PYTHON_ADAPTER, encoding="utf-8")
    comp_dir = repo_root / "specs" / "components" / "widget-maker"
    comp_dir.mkdir(parents=True)
    (comp_dir / "component.md").write_text(COMPONENT_MD, encoding="utf-8")

    bundle = {
        "component_id": "comp-widget-maker",
        "spec_bundle_hash": "sha256:" + "ab" * 32,
        "spec": "Widget maker spec.",
        "interface": "make_widget() -> str",
        "constraints": "No constraints.",
        "dependency_interfaces": {"comp-bar": INTERFACE_TEXT},
        "dependency_context": {"comp-bar": "Bar stores entries."},
        "dependency_usage": {"comp-bar": USAGE_TEXT},
        "vars": {},
        "glossary": "",
        "hint_code": None,
    }

    recorded = []

    def mock_backend(prompt, model, **params):
        recorded.append(prompt)
        nonce = re.search(r"-----BEGIN FILE ([0-9a-f]{32}):", prompt).group(1)
        text = (
            "-----BEGIN FILE " + nonce + ": widget_maker.py-----\n"
            "def make_widget():\n"
            "    return 'w'\n"
            "-----END FILE " + nonce + "-----\n"
            "-----END REPLY " + nonce + "-----\n"
        )
        return {"text": text, "model": model, "backend": "mock", "model_call_error": None}

    generator.generate(bundle, "mock-model", repo_root=repo_root, llm_backend=mock_backend)

    assert len(recorded) >= 1
    prompt = recorded[0]
    lines = prompt.split("\n")
    assert "## DEPENDENCY USAGE" in lines
    assert "## DEPENDENCY INTERFACES" in lines

    usage = section(prompt, "## DEPENDENCY USAGE")
    interfaces = section(prompt, "## DEPENDENCY INTERFACES")

    assert "### comp-bar" in usage.split("\n")
    assert USAGE_TEXT in usage
    assert "INTERFACE_MARKER_91c2" not in usage

    assert INTERFACE_TEXT in interfaces
    assert "USAGE_MARKER_7f3a" not in interfaces