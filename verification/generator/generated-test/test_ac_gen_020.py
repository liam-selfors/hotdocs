# hotdocs-criterion: sha256:dd83010bb6d7d3de779ea88bf2d7c802446a56b44dce3ae7e3ffeb4b522928ce
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
    + ", " + repr("versions") + ": {" + repr("python") + ": " + repr("3.12")
    + "}, " + repr("lockfile_sha256") + ": None, " + repr("interpreter") + ": "
    + repr("/fake/python") + "}\n"
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
    # Bundle text deliberately avoids the words the assertion looks for.
    return {
        "component_id": "comp-widget-maker",
        "spec_bundle_hash": "sha256:" + "ab" * 32,
        "spec": "Widget Maker makes widgets.",
        "interface": "make_widget(name: str) -> str",
        "constraints": "No network.",
        "dependency_interfaces": {},
        "dependency_context": {},
        "dependency_usage": {},
        "vars": {},
        "glossary": "Widget: a small thing.",
        "hint_code": None,
    }


def _fixed_instructions(prompt):
    lines = prompt.split("\n")
    end = lines.index("## SPEC") if "## SPEC" in lines else len(lines)
    return "\n".join(lines[:end])


def test_ac_gen_020_prompt_instructs_dual_access_for_dependency_values(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _plant(repo_root)

    recorded = []

    def backend(prompt, model, **params):
        recorded.append(prompt)
        nonce = re.search(r"-----BEGIN FILE ([0-9a-f]{32}):", prompt).group(1)
        text = (
            "-----BEGIN FILE " + nonce + ": widget_maker.py-----\n"
            "def make_widget(name):\n"
            "    return name\n"
            "-----END FILE " + nonce + "-----\n"
            "-----END REPLY " + nonce + "-----\n"
        )
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    bundle = _bundle()
    assert bundle["hint_code"] is None  # cold mode

    result = generator.generate(
        bundle, "mock-model", repo_root=repo_root, llm_backend=backend
    )
    assert field(result, "refused") is None
    assert len(recorded) >= 1, "mock model was never called"

    prompt = recorded[0]
    fixed = _fixed_instructions(prompt).lower()

    # The instruction lives in the generator's own fixed text, not the bundle.
    assert "depend" in fixed, "prompt does not mention dependencies"
    assert "dict" in fixed, "prompt does not mention dict access"
    assert "attr" in fixed, "prompt does not mention attribute access"
    assert any(
        k in fixed for k in ("top-level", "top level", "own return", "return value")
    ), "prompt does not extend dual access to the dependency's top-level return value"
    assert any(
        k in fixed for k in ("never", "bare", "alone", "not ")
    ), "prompt does not forbid a bare attribute access"

    # Find a single paragraph that ties these together.
    paragraphs = re.split(r"\n\s*\n", fixed)
    matching = [
        p for p in paragraphs
        if "dict" in p and "attr" in p and "depend" in p
    ]
    assert matching, "no instruction combines dependency values with dict-or-attribute access"
    assert any(
        any(k in p for k in ("top-level", "top level", "own return", "return value"))
        for p in matching
    ), "dual-access instruction does not cover the dependency's own top-level return value"