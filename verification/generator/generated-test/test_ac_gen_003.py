# hotdocs-criterion: sha256:1240c15bf7132762fd4ce35b9fe998f447edfb6b942ba80b1b269311cf7eb358
import re
from pathlib import Path

import pytest

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


def make_repo(tmp_path):
    repo_root = tmp_path / "repo"
    adapter = repo_root / "gen" / "kind-python" / "kind_python.py"
    adapter.parent.mkdir(parents=True, exist_ok=True)
    adapter.write_text(PYTHON_ADAPTER, encoding="utf-8")
    comp = repo_root / "specs" / "components" / "widget-maker" / "component.md"
    comp.parent.mkdir(parents=True, exist_ok=True)
    comp.write_text(COMPONENT_MD, encoding="utf-8")
    return repo_root


def make_backend(prompts):
    def backend(prompt, model, **params):
        prompts.append(prompt)
        nonce = re.search(r"-----BEGIN FILE ([0-9a-f]{32}):", prompt).group(1)
        text = (
            "-----BEGIN FILE " + nonce + ": widget_maker.py-----\n"
            "X = 1\n"
            "-----END FILE " + nonce + "-----\n"
            "-----END REPLY " + nonce + "-----\n"
        )
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    return backend


def make_bundle(variant):
    bundle = {
        "component_id": "comp-widget-maker",
        "spec_bundle_hash": "sha256:" + ("ab" * 32) if variant != "hint" else "sha256:" + ("cd" * 32),
        "spec": "# Widget Maker\n\nMakes widgets.",
        "interface": "make_widget() -> str",
        "constraints": "",
        "dependency_interfaces": {},
        "dependency_context": {},
        "dependency_usage": {},
        "vars": {},
        "glossary": "",
        "hint_code": None,
    }
    if variant == "rich":
        bundle["spec_bundle_hash"] = "sha256:" + ("ef" * 32)
        bundle["constraints"] = "Be fast."
        bundle["dependency_interfaces"] = {"comp-bar": "bar() -> int"}
        bundle["dependency_context"] = {"comp-bar": "Bar does bars."}
        bundle["vars"] = {"VAR-FOO-URL": "A URL."}
        bundle["glossary"] = "- **Widget** - a thing."
    if variant == "hint":
        bundle["hint_code"] = {"widget_maker.py": "X = 0\n"}
    return bundle


@pytest.mark.parametrize(
    "variant, retry_feedback",
    [
        ("plain", None),
        ("rich", ["R-WIDGET-002", "R-WIDGET-001"]),
        ("hint", None),
    ],
)
def test_prompt_version_matches_frozen_template(tmp_path, monkeypatch, variant, retry_feedback):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    repo_root = make_repo(tmp_path)
    monkeypatch.chdir(repo_root)

    prompts = []
    bundle = make_bundle(variant)
    result = generator.generate(
        bundle,
        "mock-model",
        retry_feedback,
        repo_root=repo_root,
        llm_backend=make_backend(prompts),
    )

    declared = generator.PROMPT_VERSION
    assert declared == "v12"

    # The model was actually called with the frozen template, which declares its version.
    assert len(prompts) == 1
    lines = [line.strip() for line in prompts[0].split("\n")]
    assert "PROMPT_VERSION: " + declared in lines

    assert field(result, "refused") is None
    assert field(result, "model_call_error") is None
    assert field(result, "prompt_version") == declared