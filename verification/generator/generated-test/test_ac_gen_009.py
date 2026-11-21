# hotdocs-criterion: sha256:602b6665a9c3c57e4ed6feaad2d48dd508fb29d996287e0e3ca85a08caaa8ea1
import hashlib
import json
from pathlib import Path

import pytest

import generator


SLUG = "widget-maker"
COMPONENT_ID = "comp-widget-maker"

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


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write_component_md(repo_root, sealed):
    lines = [
        "---",
        "id: " + COMPONENT_ID,
        "title: Widget Maker",
        "status: draft",
        "owners: [pipeline-team]",
        "depends_on: []",
    ]
    if sealed:
        lines.append("sealed: true")
        lines.append("source_path: legacy/widget/")
    else:
        lines.append("sealed: false")
    lines.append("---")
    lines.append("")
    lines.append("# Widget Maker")
    lines.append("")
    path = repo_root / "specs" / "components" / SLUG / "component.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def plant_python_adapter(repo_root):
    path = repo_root / "gen" / "kind-python" / "kind_python.py"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(PYTHON_ADAPTER, encoding="utf-8")


def make_bundle():
    return {
        "component_id": COMPONENT_ID,
        "spec_bundle_hash": "sha256:" + hashlib.sha256(b"ac-gen-009-bundle").hexdigest(),
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


def make_recording_backend(log_path):
    def backend(prompt, model, **params):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write("called\n")
        return {
            "text": None,
            "model": model,
            "backend": "mock",
            "model_call_error": {"category": "network", "message": "mock should not be called"},
        }

    return backend


@pytest.fixture
def repo_root(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    root = tmp_path / "repo"
    root.mkdir()
    plant_python_adapter(root)
    return root


def run_and_check(repo_root, tmp_path, expected_reason):
    log_path = tmp_path / "model_calls.log"
    backend = make_recording_backend(log_path)

    result = generator.generate(
        make_bundle(),
        "claude-sonnet-5",
        None,
        repo_root=repo_root,
        llm_backend=backend,
    )

    calls = log_path.read_text(encoding="utf-8").splitlines() if log_path.exists() else []
    assert calls == [], "mock model was called " + str(len(calls)) + " time(s)"

    assert field(result, "files") == {}
    assert field(result, "model_call_error") is None
    refused = field(result, "refused")
    assert isinstance(refused, str)
    assert expected_reason in refused
    assert field(result, "cache_hit") is False


def test_sealed_component_refused_without_model_call(repo_root, tmp_path):
    write_component_md(repo_root, sealed=True)

    run_and_check(repo_root, tmp_path, "sealed-component")

    assert not (repo_root / "legacy" / "widget").exists()


def test_pinned_override_refused_without_model_call(repo_root, tmp_path):
    write_component_md(repo_root, sealed=False)
    gen_dir = repo_root / "gen" / SLUG
    gen_dir.mkdir(parents=True, exist_ok=True)
    (gen_dir / "widget_maker.py").write_text("PINNED = True\n", encoding="utf-8")
    (gen_dir / ".overrides.json").write_text(json.dumps(["widget_maker.py"]), encoding="utf-8")

    run_and_check(repo_root, tmp_path, "pinned-override")

    assert (gen_dir / "widget_maker.py").read_text(encoding="utf-8") == "PINNED = True\n"