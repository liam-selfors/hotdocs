# hotdocs-criterion: sha256:0f6123ae5ed6e6c79c805704b0f2418c290f1abfcb943b86460c726e03a38d04
import dataclasses
import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path

import generator


SPEC_HASH = "sha256:" + hashlib.sha256(b"widget-maker-bundle-ac-gen-006").hexdigest()
MODEL = "mock-model"
RETRY = ["R-WID-001"]
FILES = {"widget_maker.py": "def make():\n    return 1\n"}


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def load_module(path, module_name):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def load_cache_manager():
    gen = next(p for p in Path(generator.__file__).resolve().parents if p.name == "gen")
    base = gen / "cache-manager"
    flat = base / "cache_manager.py"
    path = flat if flat.is_file() else base / "cache_manager" / "__init__.py"
    return load_module(path, "cache_manager")


class Bundle(dict):
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)


def make_bundle():
    return Bundle(
        component_id="comp-widget-maker",
        spec_bundle_hash=SPEC_HASH,
        spec="# Widget Maker\n\nR-WID-001: make() MUST return 1.",
        interface="make() -> int",
        constraints="None.",
        dependency_interfaces={},
        dependency_context={},
        dependency_usage={},
        vars={},
        glossary="",
        hint_code=None,
    )


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


def plant_repo(repo_root):
    adapter = repo_root / "gen" / "kind-python" / "kind_python.py"
    adapter.parent.mkdir(parents=True, exist_ok=True)
    adapter.write_text(PYTHON_ADAPTER, encoding="utf-8")
    comp = repo_root / "specs" / "components" / "widget-maker" / "component.md"
    comp.parent.mkdir(parents=True, exist_ok=True)
    comp.write_text(COMPONENT_MD, encoding="utf-8")


def make_backend(calls):
    def backend(prompt, model, **params):
        calls.append(model)
        nonce = re.search(r"-----BEGIN FILE ([0-9a-f]{32}):", prompt).group(1)
        parts = []
        for path, content in FILES.items():
            parts.append("-----BEGIN FILE " + nonce + ": " + path + "-----\n")
            parts.append(content)
            parts.append("-----END FILE " + nonce + "-----\n")
        parts.append("-----END REPLY " + nonce + "-----\n")
        return {"text": "".join(parts), "model": model, "backend": "mock", "model_call_error": None}

    return backend


def make_key(cm, model, retry_feedback):
    digest = hashlib.sha256(
        json.dumps(sorted(retry_feedback or []), sort_keys=True).encode("utf-8")
    ).hexdigest()
    return cm.CacheKey(
        spec_bundle_hash=SPEC_HASH,
        gate_inputs_hash="sha256:" + digest,
        gate_version=generator.GATE_VERSION,
        model_pin=model,
    )


def with_error(result):
    err = {"category": "network", "message": "mock failure"}
    if isinstance(result, dict):
        out = dict(result)
        out.update(files={}, model_call_error=err, refused=None, cache_hit=False, model="mock-model-err")
        return out
    return dataclasses.replace(
        result, files={}, model_call_error=err, refused=None, cache_hit=False, model="mock-model-err"
    )


def test_ac_gen_006_only_commit_cache_writes_cache(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(tmp_path)
    plant_repo(repo_root)

    cm = load_cache_manager()
    key = make_key(cm, MODEL, RETRY)

    assert isinstance(cm.get(key, repo_root=repo_root), cm.Miss)

    # Scenario 1: generate does not write the cache.
    calls = []
    bundle = make_bundle()
    result = generator.generate(
        bundle, MODEL, list(RETRY), repo_root=repo_root, llm_backend=make_backend(calls)
    )
    assert len(calls) == 1
    assert field(result, "model_call_error") is None
    assert field(result, "refused") is None
    assert dict(field(result, "files")) == FILES
    assert field(result, "cache_hit") is False
    assert isinstance(cm.get(key, repo_root=repo_root), cm.Miss)
    assert cm.stats(repo_root=repo_root)["entry_count"] == 0

    # Scenario 2: commit_cache writes it; a second generate is a hit.
    generator.commit_cache(result, repo_root)
    stored = cm.get(key, repo_root=repo_root)
    assert not isinstance(stored, cm.Miss)
    assert field(stored, "gate_type") == "generator"
    entries_after_commit = cm.stats(repo_root=repo_root)["entry_count"]
    assert entries_after_commit >= 1

    calls2 = []
    second = generator.generate(
        make_bundle(), MODEL, list(RETRY), repo_root=repo_root, llm_backend=make_backend(calls2)
    )
    assert calls2 == []
    assert field(second, "cache_hit") is True
    assert dict(field(second, "files")) == FILES

    # Scenario 3: a result with model_call_error is never written.
    err_result = with_error(result)
    err_key = make_key(cm, "mock-model-err", RETRY)
    assert isinstance(cm.get(err_key, repo_root=repo_root), cm.Miss)
    generator.commit_cache(err_result, repo_root)
    assert isinstance(cm.get(err_key, repo_root=repo_root), cm.Miss)
    assert cm.stats(repo_root=repo_root)["entry_count"] == entries_after_commit