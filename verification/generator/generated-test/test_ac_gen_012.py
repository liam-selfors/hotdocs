# hotdocs-criterion: sha256:28bed23b5dd368f444c01c6d1b39bcc1808e0d1e814d70a11bc776b088aade3f
"""AC-GEN-012: a hanging model call ends in model_call_error after the
SDK's own timeout, with exactly one call attempt and no internal retry
(R-GEN-011)."""

import threading
import time
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
    "depends_on: []\n"
    "sealed: false\n"
    "---\n"
    "\n"
    "# Widget Maker\n"
)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _plant_repo(repo_root):
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
        "interface": "make_widget() -> str",
        "constraints": "",
        "dependency_interfaces": {},
        "dependency_context": {},
        "dependency_usage": {},
        "vars": {},
        "glossary": "",
        "hint_code": None,
        "spec_bundle_parts": {},
    }


def test_ac_gen_012_hanging_model_times_out_once_without_retry(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _plant_repo(repo_root)

    call_log = tmp_path / "calls.log"

    def hanging_backend(prompt, model, **params):
        # Record the attempt, then behave as a model that never responds
        # does once the SDK's own default timeout gives up on it: the call
        # blocks, then surfaces a timeout error rather than any text.
        with open(call_log, "a", encoding="utf-8") as fh:
            fh.write("call\n")
        time.sleep(0.5)
        return {
            "text": None,
            "model": model,
            "backend": "mock-hang",
            "model_call_error": {
                "category": "timeout",
                "message": "model did not respond before the timeout",
            },
        }

    outcome = {}

    def run():
        try:
            outcome["result"] = generator.generate(
                _bundle(),
                "anthropic:claude-sonnet-5",
                repo_root=repo_root,
                llm_backend=hanging_backend,
            )
        except BaseException as exc:  # surfaced below
            outcome["error"] = exc

    worker = threading.Thread(target=run, daemon=True)
    worker.start()
    worker.join(timeout=120)

    assert not worker.is_alive(), "generate did not complete: unbounded hang"
    assert "error" not in outcome, "generate raised: " + repr(outcome.get("error"))
    result = outcome["result"]

    error = field(result, "model_call_error")
    assert error is not None
    assert field(error, "category")
    assert field(error, "message") is not None
    assert field(result, "files") == {}
    assert field(result, "refused") is None
    assert field(result, "cache_hit") is False

    calls = call_log.read_text(encoding="utf-8").splitlines() if call_log.exists() else []
    assert len(calls) == 1, "expected exactly one call attempt, got " + repr(len(calls))