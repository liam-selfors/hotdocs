# hotdocs-criterion: sha256:b1d328bbc3c7fe1f3a940cd160ab067e6e146f3ecb68edf72792128739183a9e
"""AC-GEN-012 (covers R-GEN-011): generate never retries an llm-endpoint call.

A mock model that "hangs" until the SDK's own default timeout gives up is
simulated by a backend that blocks briefly and then reports the timeout
the endpoint's default timeout would produce. generate must complete with
model_call_error set, and the mock must record exactly one call attempt.
"""

import threading
import time
from pathlib import Path

import generator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


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


def _make_repo(repo_root):
    comp_dir = repo_root / "specs" / "components" / "widget-maker"
    comp_dir.mkdir(parents=True)
    (comp_dir / "component.md").write_text(COMPONENT_MD, encoding="utf-8")
    adapter_dir = repo_root / "gen" / "kind-python"
    adapter_dir.mkdir(parents=True)
    (adapter_dir / "kind_python.py").write_text(PYTHON_ADAPTER, encoding="utf-8")


def _bundle():
    return {
        "component_id": "comp-widget-maker",
        "spec_bundle_hash": "sha256:" + "ac0012" * 10 + "abcd",
        "spec": "# Widget Maker\n\nMakes widgets.",
        "interface": "make_widget() -> str",
        "constraints": "None.",
        "dependency_interfaces": {},
        "dependency_context": {},
        "dependency_usage": {},
        "vars": {},
        "glossary": "",
        "hint_code": None,
    }


def test_ac_gen_012_hanging_model_called_once_no_retry(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _make_repo(repo_root)

    call_log = tmp_path / "calls.log"
    call_log.write_text("", encoding="utf-8")

    def hanging_backend(prompt, model, **params):
        # Record the attempt first, then "hang" until the SDK's own default
        # timeout gives up, reported as the endpoint's timeout error.
        with open(call_log, "a", encoding="utf-8") as fh:
            fh.write("call\n")
        time.sleep(0.5)
        return {
            "text": None,
            "model": model,
            "backend": "mock-hang",
            "model_call_error": {"category": "timeout", "message": "model call timed out"},
        }

    outcome = {}

    def run():
        try:
            outcome["result"] = generator.generate(
                _bundle(),
                "claude-sonnet-5",
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
    assert error is not None, "expected model_call_error to be set"
    assert field(result, "files") == {}
    assert field(result, "cache_hit") is False
    assert field(result, "refused") is None

    calls = [line for line in call_log.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(calls) == 1, "expected exactly one model call attempt, got " + repr(len(calls))