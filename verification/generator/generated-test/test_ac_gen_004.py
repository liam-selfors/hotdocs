# hotdocs-criterion: sha256:5ccd32bdc9a981a9eedbb538c7afe0544b2fc462b33a4ad0c4f612ce407dbdbe
import json
import re

import generator


PYTHON_ADAPTER_SOURCE = (
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


def make_bundle():
    return {
        "component_id": "comp-widget-maker",
        "spec_bundle_hash": "sha256:" + "ab" * 32,
        "spec": "Widget Maker makes widgets.",
        "interface": "make_widget() -> str",
        "constraints": "None.",
        "dependency_interfaces": {},
        "dependency_context": {},
        "dependency_usage": {},
        "vars": {},
        "glossary": "",
        "hint_code": None,
    }


def make_mock_backend(log_path):
    def backend(prompt, model, **params):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"model": model}) + "\n")
        nonce = re.search(r"-----BEGIN FILE ([0-9a-f]{32}):", prompt).group(1)
        text = (
            "-----BEGIN FILE " + nonce + ": widget_maker.py-----\n"
            "def make_widget():\n"
            "    return \"widget\"\n"
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


def test_ac_gen_004_model_identifier_passed_through(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)

    repo_root = tmp_path / "repo"
    adapter_dir = repo_root / "gen" / "kind-python"
    adapter_dir.mkdir(parents=True)
    (adapter_dir / "kind_python.py").write_text(PYTHON_ADAPTER_SOURCE, encoding="utf-8")

    comp_dir = repo_root / "specs" / "components" / "widget-maker"
    comp_dir.mkdir(parents=True)
    (comp_dir / "component.md").write_text(COMPONENT_MD, encoding="utf-8")

    log_path = tmp_path / "mock_calls.log"
    backend = make_mock_backend(log_path)

    bundle = make_bundle()
    model_a = "test-model-alpha-7781"
    model_b = "test-model-beta-4412"

    result_a = generator.generate(bundle, model_a, repo_root=repo_root, llm_backend=backend)
    result_b = generator.generate(bundle, model_b, repo_root=repo_root, llm_backend=backend)

    assert field(result_a, "model_call_error") is None
    assert field(result_b, "model_call_error") is None
    assert field(result_a, "refused") is None
    assert field(result_b, "refused") is None
    assert field(result_a, "cache_hit") is False
    assert field(result_b, "cache_hit") is False

    lines = [l for l in log_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(lines) == 2
    recorded = [json.loads(l)["model"] for l in lines]
    assert recorded[0] == model_a
    assert recorded[1] == model_b
    assert recorded[0] != recorded[1]