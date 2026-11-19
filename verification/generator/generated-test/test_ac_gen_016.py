# hotdocs-criterion: sha256:fd7d3aa456e68ce3aba03b5894c64b3154c5461e4e8313aebf5d317cde4fa37d
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
        "spec": "A component that makes widgets.",
        "interface": "make() -> int",
        "constraints": "Be deterministic.",
        "dependency_interfaces": {},
        "dependency_context": {},
        "dependency_usage": {},
        "vars": {},
        "glossary": "",
        "hint_code": None,
    }


def test_ac_gen_016_prompt_instructs_flat_or_package_layout(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _plant(repo_root)

    recorded = []

    def mock_backend(prompt, model, **params):
        recorded.append(prompt)
        nonce = re.search(r"-----BEGIN FILE ([0-9a-f]{32}):", prompt).group(1)
        text = (
            "-----BEGIN FILE " + nonce + ": widget_maker.py-----\n"
            "def make():\n"
            "    return 1\n"
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
        _bundle(), "mock-model", repo_root=repo_root, llm_backend=mock_backend
    )

    assert field(result, "refused") is None
    assert len(recorded) == 1, "the mock model must be called exactly once"
    prompt = recorded[0]

    # The layout instruction is fixed scaffolding, preceding every bundle-derived section.
    marker = "\n## SPEC\n"
    assert marker in prompt
    instructions = prompt[: prompt.index(marker)]

    # Names the real module as a flat module and as a package.
    assert "widget_maker.py" in instructions
    assert "widget_maker/" in instructions
    assert "__init__.py" in instructions
    # Directly under gen/<component>/.
    assert "gen/widget-maker" in instructions
    # Forbids a deeper src/-style layout.
    assert re.search(r"\bsrc\b", instructions), "prompt must rule out a src/-style layout"