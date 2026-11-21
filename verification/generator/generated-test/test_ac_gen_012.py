# hotdocs-criterion: sha256:3e0f3c8962e4ab6a3665679b3052c0945a1cbec4f1770d09a650592afee9620d
import threading
from pathlib import Path

import generator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


FAKE_PYTHON_ADAPTER = (
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
        "spec_bundle_hash": "sha256:" + "ab" * 32,
        "spec": "Widget Maker makes widgets.",
        "interface": "make_widget() -> str",
        "constraints": "",
        "dependency_interfaces": {},
        "dependency_context": {},
        "dependency_usage": {},
        "vars": {},
        "glossary": "",
        "hint_code": None,
    }


def test_ac_gen_012_hanging_model_no_internal_retry(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _plant_repo(repo_root)
    log_path = tmp_path / "calls.log"

    def hanging_backend(prompt, model, **params):
        # Record the attempt, then behave as the SDK does once its own
        # default timeout elapses on a model that never responds.
        with open(str(log_path), "a", encoding="utf-8") as fh:
            fh.write("call\n")
        threading.Event().wait(0.2)
        return {
            "text": None,
            "model": model,
            "backend": "mock-hang",
            "model_call_error": {"category": "timeout", "message": "timed out"},
        }

    outcome = {}

    def run():
        try:
            outcome["result"] = generator.generate(
                _bundle(),
                "anthropic:claude-sonnet-5",
                None,
                repo_root=repo_root,
                llm_backend=hanging_backend,
            )
        except BaseException as exc:  # pragma: no cover - reported below
            outcome["error"] = exc

    worker = threading.Thread(target=run, daemon=True)
    worker.start()
    worker.join(timeout=120)

    assert not worker.is_alive(), "generate did not complete: unbounded hang"
    assert "error" not in outcome, "generate raised: " + repr(outcome.get("error"))
    result = outcome["result"]

    assert field(result, "model_call_error") is not None
    assert field(result, "files") == {}
    assert field(result, "cache_hit") is False
    assert field(result, "refused") is None

    assert log_path.exists(), "mock model was never called"
    calls = [line for line in log_path.read_text(encoding="utf-8").splitlines() if line]
    assert len(calls) == 1, "expected exactly one call attempt, got " + repr(len(calls))