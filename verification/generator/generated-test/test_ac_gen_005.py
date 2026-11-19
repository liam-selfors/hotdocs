# hotdocs-criterion: sha256:a3905129bd7c667b82adee210b40314e5865be86a55eb8fa1d5839832c19f44f
import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path

import generator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def load_module(path, module_name):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def load_tool_cache_manager():
    gen = next(p for p in Path(generator.__file__).resolve().parents if p.name == "gen")
    base = gen / "cache-manager"
    path = base / "cache_manager.py" if (base / "cache_manager.py").is_file() else base / "cache_manager" / "__init__.py"
    return load_module(path, "cache_manager")


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


def test_cache_hit_returns_cached_result_without_model_call(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)

    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    adapter_dir = repo_root / "gen" / "kind-python"
    adapter_dir.mkdir(parents=True)
    (adapter_dir / "kind_python.py").write_text(PYTHON_ADAPTER, encoding="utf-8")

    comp_dir = repo_root / "specs" / "components" / "widget-maker"
    comp_dir.mkdir(parents=True)
    (comp_dir / "component.md").write_text(COMPONENT_MD, encoding="utf-8")

    log_path = tmp_path / "model_calls.log"

    def mock_backend(prompt, model, **params):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write("called\n")
        nonce = re.search(r"-----BEGIN FILE ([0-9a-f]{32}):", prompt).group(1)
        text = (
            "-----BEGIN FILE " + nonce + ": widget_maker.py-----\n"
            "FROM_MODEL = True\n"
            "-----END FILE " + nonce + "-----\n"
            "-----END REPLY " + nonce + "-----\n"
        )
        return {"text": text, "model": model, "backend": "mock", "model_call_error": None}

    spec_bundle_hash = "sha256:" + "a" * 64
    bundle = {
        "component_id": "comp-widget-maker",
        "spec_bundle_hash": spec_bundle_hash,
        "spec": "Widget maker spec.",
        "interface": "def make_widget() -> str",
        "constraints": "None.",
        "dependency_interfaces": {},
        "dependency_context": {},
        "dependency_usage": {},
        "vars": {},
        "glossary": "",
        "hint_code": None,
    }
    model = "mock-model"

    cache_manager = load_tool_cache_manager()

    gate_inputs_hash = "sha256:" + hashlib.sha256(
        json.dumps(sorted([]), sort_keys=True).encode("utf-8")
    ).hexdigest()
    key = cache_manager.CacheKey(
        spec_bundle_hash=spec_bundle_hash,
        gate_inputs_hash=gate_inputs_hash,
        gate_version=generator.GATE_VERSION,
        model_pin=model,
    )

    cached_files = {"widget_maker.py": "CACHED = True\n"}
    payload = {
        "component_id": "comp-widget-maker",
        "spec_bundle_hash": spec_bundle_hash,
        "model": model,
        "prompt_version": generator.PROMPT_VERSION,
        "cache_hit": False,
        "files": cached_files,
        "model_call_error": None,
        "refused": None,
        "retry_feedback": None,
        "mode": "single",
        "transcript_sha256": None,
        "turns": 1,
        "tool_calls": 0,
        "isolation": None,
    }
    cached = cache_manager.CachedResult(
        gate_type="generator",
        payload=payload,
        stored_at=cache_manager.now_iso(),
    )
    cache_manager.put(key, cached, repo_root=repo_root)

    # Sanity: the cache really holds the entry before generate runs.
    pre = cache_manager.get(key, repo_root=repo_root)
    assert not isinstance(pre, cache_manager.Miss)

    result = generator.generate(
        bundle, model, None, repo_root=repo_root, llm_backend=mock_backend
    )

    assert not log_path.exists() or log_path.read_text(encoding="utf-8") == ""
    assert field(result, "cache_hit") is True
    assert dict(field(result, "files")) == cached_files
    assert field(result, "model_call_error") is None
    assert field(result, "refused") is None