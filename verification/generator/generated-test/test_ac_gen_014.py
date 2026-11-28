# hotdocs-criterion: sha256:1ed310bd8bf06035a08315bb97b819b78a3cbc4c49a511e6d378316e7da1d703
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
    "    return {\"ok\": True, \"reason\": \"\", \"versions\": {\"python\": \"3.12\"}, \"lockfile_sha256\": None, \"interpreter\": \"/fake/python\"}\n"
)

COMPONENT_MD = (
    "---\n"
    "id: comp-widget-maker\n"
    "title: Widget Maker\n"
    "status: draft\n"
    "owners: [pipeline-team]\n"
    "depends_on: [comp-bar-store]\n"
    "sealed: false\n"
    "---\n"
    "\n"
    "# Widget Maker\n"
)

USAGE_TEXT = (
    "Module: bar_store_usage_marker_q7\n"
    "\n"
    "def fetch_usage_marker_z9(key: str, *, repo_root: Path = None) -> dict:\n"
    "    \"\"\"Return the stored entry for key.\"\"\""
)

INTERFACE_TEXT = "# Library\n\nINTERFACE_ONLY_MARKER_k3 store(key) -> None"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def section(prompt, heading):
    lines = prompt.split("\n")
    start = lines.index(heading) + 1
    end = next((i for i in range(start, len(lines)) if lines[i].startswith("## ")), len(lines))
    return "\n".join(lines[start:end]).rstrip("\n")


def _setup_repo(repo_root):
    adapter = repo_root / "gen" / "kind-python" / "kind_python.py"
    adapter.parent.mkdir(parents=True, exist_ok=True)
    adapter.write_text(PYTHON_ADAPTER, encoding="utf-8")
    comp = repo_root / "specs" / "components" / "widget-maker" / "component.md"
    comp.parent.mkdir(parents=True, exist_ok=True)
    comp.write_text(COMPONENT_MD, encoding="utf-8")


def _bundle():
    return {
        "component_id": "comp-widget-maker",
        "spec_bundle_hash": "sha256:" + "ab" * 32,
        "spec": "# Widget Maker\n\nMakes widgets.",
        "interface": "# Library\n\nmake_widget() -> str",
        "constraints": "No network.",
        "dependency_interfaces": {"comp-bar-store": INTERFACE_TEXT},
        "dependency_context": {"comp-bar-store": "Stores bars."},
        "dependency_usage": {"comp-bar-store": USAGE_TEXT},
        "vars": {},
        "glossary": "Glossary text.",
        "hint_code": None,
        "spec_bundle_parts": {},
    }


def test_ac_gen_014_dependency_usage_is_distinct_section(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _setup_repo(repo_root)
    monkeypatch.chdir(tmp_path)

    recorded = []

    def mock_backend(prompt, model, **params):
        recorded.append(prompt)
        nonce = re.search(r"-----BEGIN FILE ([0-9a-f]{32}):", prompt).group(1)
        text = (
            "-----BEGIN FILE " + nonce + ": widget_maker.py-----\n"
            "def make_widget():\n"
            "    return \"widget\"\n"
            "-----END FILE " + nonce + "-----\n"
            "-----END REPLY " + nonce + "-----\n"
        )
        return {"text": text, "model": model, "backend": "mock", "model_call_error": None}

    result = generator.generate(
        _bundle(), "claude-sonnet-5", repo_root=repo_root, llm_backend=mock_backend
    )

    assert len(recorded) >= 1, "mock model was never called"
    assert field(result, "refused") is None
    prompt = recorded[-1]
    lines = prompt.split("\n")

    assert "## DEPENDENCY USAGE" in lines
    assert "## DEPENDENCY INTERFACES" in lines
    assert lines.index("## DEPENDENCY USAGE") != lines.index("## DEPENDENCY INTERFACES")

    usage_section = section(prompt, "## DEPENDENCY USAGE")
    interfaces_section = section(prompt, "## DEPENDENCY INTERFACES")

    # The usage content appears in its own section, keyed by dependency.
    assert "### comp-bar-store" in usage_section.split("\n")
    assert USAGE_TEXT in usage_section
    assert "bar_store_usage_marker_q7" in usage_section
    assert "fetch_usage_marker_z9" in usage_section

    # Never merged with dependency_interfaces.
    assert "bar_store_usage_marker_q7" not in interfaces_section
    assert "fetch_usage_marker_z9" not in interfaces_section
    assert "INTERFACE_ONLY_MARKER_k3" in interfaces_section
    assert "INTERFACE_ONLY_MARKER_k3" not in usage_section