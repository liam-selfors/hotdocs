# hotdocs-criterion: sha256:e49dc4c9aff3a7d6f21d43cef9e2b92f12100e701ccaa1e045035d9f6d38ce1f
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
    "depends_on: [comp-bar]\n"
    "sealed: false\n"
    "---\n"
    "\n"
    "# Widget Maker\n"
)

USAGE_TEXT = (
    "Module: bar_usage_marker_module\n"
    "\n"
    "def bar_lookup_usage_marker(key: str) -> dict\n"
    "    Return the entry stored under key."
)

INTERFACE_TEXT = "INTERFACE_MARKER_FOR_BAR: bar_lookup(key) returns an Entry."


class Bundle(dict):
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def section(prompt, heading):
    lines = prompt.split("\n")
    start = lines.index(heading) + 1
    end = next((i for i in range(start, len(lines)) if lines[i].startswith("## ")), len(lines))
    return "\n".join(lines[start:end]).rstrip("\n")


def _plant(repo_root):
    adapter = repo_root / "gen" / "kind-python" / "kind_python.py"
    adapter.parent.mkdir(parents=True, exist_ok=True)
    adapter.write_text(PYTHON_ADAPTER, encoding="utf-8")
    comp = repo_root / "specs" / "components" / "widget-maker" / "component.md"
    comp.parent.mkdir(parents=True, exist_ok=True)
    comp.write_text(COMPONENT_MD, encoding="utf-8")


def test_ac_gen_014_dependency_usage_is_its_own_section(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _plant(repo_root)
    monkeypatch.chdir(repo_root)

    log_dir = tmp_path / "log"
    log_dir.mkdir()
    recorded = []

    def mock_backend(prompt, model, **params):
        recorded.append(prompt)
        (log_dir / ("prompt_" + str(len(recorded)) + ".txt")).write_text(prompt, encoding="utf-8")
        nonce = re.search(r"-----BEGIN FILE ([0-9a-f]{32}):", prompt).group(1)
        text = (
            "-----BEGIN FILE " + nonce + ": widget_maker.py-----\n"
            "x = 1\n"
            "-----END FILE " + nonce + "-----\n"
            "-----END REPLY " + nonce + "-----\n"
        )
        return {"text": text, "model": model, "backend": "mock", "model_call_error": None}

    bundle = Bundle(
        component_id="comp-widget-maker",
        spec_bundle_hash="sha256:" + "ab" * 32,
        spec="Widget Maker makes widgets.",
        interface="make_widget() -> dict",
        constraints="No network.",
        dependency_interfaces={"comp-bar": INTERFACE_TEXT},
        dependency_context={"comp-bar": "Bar stores entries."},
        dependency_usage={"comp-bar": USAGE_TEXT},
        vars={},
        glossary="Glossary text.",
        hint_code=None,
    )

    result = generator.generate(
        bundle, "mock-model", repo_root=repo_root, llm_backend=mock_backend
    )

    assert field(result, "refused") is None
    assert len(recorded) >= 1
    prompt = (log_dir / "prompt_1.txt").read_text(encoding="utf-8")
    lines = prompt.split("\n")

    assert "## DEPENDENCY USAGE" in lines
    assert "## DEPENDENCY INTERFACES" in lines

    usage_section = section(prompt, "## DEPENDENCY USAGE")
    interfaces_section = section(prompt, "## DEPENDENCY INTERFACES")

    assert "### comp-bar" in usage_section.split("\n")
    assert "bar_usage_marker_module" in usage_section
    assert "bar_lookup_usage_marker(key: str) -> dict" in usage_section
    assert INTERFACE_TEXT not in usage_section

    assert INTERFACE_TEXT in interfaces_section
    assert "bar_usage_marker_module" not in interfaces_section
    assert "bar_lookup_usage_marker" not in interfaces_section

    assert lines.index("## DEPENDENCY USAGE") != lines.index("## DEPENDENCY INTERFACES")