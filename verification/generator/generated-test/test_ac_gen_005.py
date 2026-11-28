# hotdocs-criterion: sha256:c7632ae7185cf56bfcc5ba809e2a627c9877a38aafe15afaf23978e7be86807c
"""AC-GEN-005: a cache hit returns the cached result and never calls the model.

Covers R-GEN-005.
"""

import dataclasses
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import generator


def load_module(path, module_name):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _load_cache_manager():
    gen = next(p for p in Path(generator.__file__).resolve().parents if p.name == "gen")
    base = gen / "cache-manager"
    path = (
        base / "cache_manager.py"
        if (base / "cache_manager.py").is_file()
        else base / "cache_manager" / "__init__.py"
    )
    return load_module(path, "cache_manager")


@dataclasses.dataclass
class FakeSpecBundle:
    component_id: str
    spec_bundle_hash: str
    spec: str
    interface: str
    constraints: str
    dependency_interfaces: dict = dataclasses.field(default_factory=dict)
    dependency_context: dict = dataclasses.field(default_factory=dict)
    dependency_usage: dict = dataclasses.field(default_factory=dict)
    vars: dict = dataclasses.field(default_factory=dict)
    glossary: str = ""
    hint_code: object = None
    spec_bundle_parts: dict = dataclasses.field(default_factory=dict)

    def __getitem__(self, key):
        return getattr(self, key)

    def get(self, key, default=None):
        return getattr(self, key, default)


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


def _plant_repo(repo_root):
    comp_dir = repo_root / "specs" / "components" / "widget-maker"
    comp_dir.mkdir(parents=True)
    (comp_dir / "component.md").write_text(COMPONENT_MD, encoding="utf-8")
    adapter_dir = repo_root / "gen" / "kind-python"
    adapter_dir.mkdir(parents=True)
    (adapter_dir / "kind_python.py").write_text(PYTHON_ADAPTER, encoding="utf-8")


def test_cache_hit_returns_cached_result_without_model_call(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _plant_repo(repo_root)
    monkeypatch.chdir(repo_root)

    model_log = tmp_path / "model_calls.log"

    component_id = "comp-widget-maker"
    spec_bundle_hash = "sha256:" + hashlib.sha256(b"widget-maker bundle").hexdigest()
    model = "claude-sonnet-5"
    retry_feedback = ["R-WIDGET-001"]

    bundle = FakeSpecBundle(
        component_id=component_id,
        spec_bundle_hash=spec_bundle_hash,
        spec="# Widget Maker\n\nR-WIDGET-001 makes widgets.",
        interface="make_widget() -> str",
        constraints="None.",
        glossary="Glossary.",
    )

    gate_inputs_hash = "sha256:" + hashlib.sha256(
        json.dumps(sorted(retry_feedback or []), sort_keys=True).encode("utf-8")
    ).hexdigest()

    cache_manager = _load_cache_manager()
    key = cache_manager.CacheKey(
        spec_bundle_hash=spec_bundle_hash,
        gate_inputs_hash=gate_inputs_hash,
        gate_version=generator.GATE_VERSION,
        model_pin=model,
    )
    cached_files = {"widget_maker.py": "CACHED = 'from the cache'\n"}
    payload = {
        "component_id": component_id,
        "spec_bundle_hash": spec_bundle_hash,
        "model": model,
        "prompt_version": "v12",
        "cache_hit": False,
        "files": dict(cached_files),
        "model_call_error": None,
        "refused": None,
        "retry_feedback": list(retry_feedback),
        "mode": "single",
        "transcript_sha256": None,
        "turns": 1,
        "tool_calls": 0,
        "isolation": None,
    }
    cache_manager.put(
        key,
        cache_manager.CachedResult(
            gate_type="generator",
            payload=payload,
            stored_at=cache_manager.now_iso(),
        ),
        repo_root=repo_root,
    )
    # Sanity: the cache really holds the entry under the documented key.
    assert not isinstance(cache_manager.get(key, repo_root=repo_root), cache_manager.Miss)

    def mock_model(prompt, model, **params):
        with open(str(model_log), "a", encoding="utf-8") as fh:
            fh.write("called\n")
        import re

        nonce = re.search(r"-----BEGIN FILE ([0-9a-f]{32}):", prompt).group(1)
        text = (
            "-----BEGIN FILE " + nonce + ": widget_maker.py-----\n"
            "FRESH = 'from the model'\n"
            "-----END FILE " + nonce + "-----\n"
            "-----END REPLY " + nonce + "-----\n"
        )
        return {"text": text, "model": model, "backend": "mock", "model_call_error": None}

    result = generator.generate(
        bundle,
        model,
        list(retry_feedback),
        repo_root=repo_root,
        llm_backend=mock_model,
    )

    # The mock model is never called.
    assert not model_log.exists() or model_log.read_text(encoding="utf-8") == ""

    # The cached result is returned.
    assert field(result, "cache_hit") is True
    assert dict(field(result, "files")) == cached_files
    assert field(result, "model_call_error") is None
    assert field(result, "refused") is None
    assert field(result, "component_id") == component_id