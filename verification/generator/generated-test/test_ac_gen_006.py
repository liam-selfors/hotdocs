# hotdocs-criterion: sha256:092f7672f8827a0e7f861dee1d65a5317d6854dbe9695db327c2b37d9e47e0e7
import generator

import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest


COMPONENT_ID = "comp-widget-maker"
MODEL = "claude-sonnet-5"


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


def make_repo(root):
    root.mkdir(parents=True, exist_ok=True)
    adapter = root / "gen" / "kind-python" / "kind_python.py"
    adapter.parent.mkdir(parents=True, exist_ok=True)
    adapter.write_text(FAKE_PYTHON_ADAPTER, encoding="utf-8")
    comp = root / "specs" / "components" / "widget-maker" / "component.md"
    comp.parent.mkdir(parents=True, exist_ok=True)
    comp.write_text(COMPONENT_MD, encoding="utf-8")
    return root


def make_bundle(hash_seed):
    return {
        "component_id": COMPONENT_ID,
        "spec_bundle_hash": "sha256:" + hashlib.sha256(hash_seed.encode("utf-8")).hexdigest(),
        "spec": "Widget maker spec.",
        "interface": "VALUE: int",
        "constraints": "None.",
        "dependency_interfaces": {},
        "dependency_context": {},
        "dependency_usage": {},
        "vars": {},
        "glossary": "",
        "hint_code": None,
    }


def make_key(cache_manager, bundle, retry_feedback, model):
    digest = hashlib.sha256(
        json.dumps(sorted(retry_feedback or []), sort_keys=True).encode("utf-8")
    ).hexdigest()
    return cache_manager.CacheKey(
        spec_bundle_hash=bundle["spec_bundle_hash"],
        gate_inputs_hash="sha256:" + digest,
        gate_version=generator.GATE_VERSION,
        model_pin=model,
    )


def is_miss(cache_manager, value):
    return isinstance(value, cache_manager.Miss) or type(value).__name__ == "Miss"


def make_backend(log_path, fail=False):
    def backend(prompt, model, **params):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write("call\n")
        if fail:
            return {
                "text": None,
                "model": model,
                "backend": "mock",
                "model_call_error": {"category": "network", "message": "mock network failure"},
            }
        nonce = re.search(r"-----BEGIN FILE ([0-9a-f]{32}):", prompt).group(1)
        text = (
            "-----BEGIN FILE " + nonce + ": widget_maker.py-----\n"
            + "VALUE = 1\n"
            + "-----END FILE " + nonce + "-----\n"
            + "-----END REPLY " + nonce + "-----\n"
        )
        return {"text": text, "model": model, "backend": "mock", "model_call_error": None}

    return backend


def call_count(log_path):
    if not Path(log_path).exists():
        return 0
    return len([l for l in Path(log_path).read_text(encoding="utf-8").splitlines() if l.strip()])


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_generate_does_not_write_cache_and_commit_cache_does(env):
    cache_manager = load_cache_manager()
    repo_root = make_repo(env / "repo")
    log_path = env / "model_calls.log"
    bundle = make_bundle("ac-gen-006-success")
    retry_feedback = ["R-WIDGET-002", "R-WIDGET-001"]
    key = make_key(cache_manager, bundle, retry_feedback, MODEL)

    assert is_miss(cache_manager, cache_manager.get(key, repo_root=repo_root))

    backend = make_backend(log_path)
    result = generator.generate(
        bundle, MODEL, list(retry_feedback), repo_root=repo_root, llm_backend=backend
    )

    assert call_count(log_path) == 1
    assert field(result, "model_call_error") is None
    assert field(result, "refused") is None
    assert field(result, "cache_hit") is False
    files = field(result, "files")
    assert files
    assert "widget_maker.py" in files
    assert files["widget_maker.py"] == "VALUE = 1\n"

    # generate() itself must not have written the cache
    assert is_miss(cache_manager, cache_manager.get(key, repo_root=repo_root))

    generator.commit_cache(result, repo_root)

    stored = cache_manager.get(key, repo_root=repo_root)
    assert not is_miss(cache_manager, stored)
    assert field(stored, "gate_type") == "generator"
    payload = field(stored, "payload")
    assert field(payload, "files") == files

    second = generator.generate(
        bundle, MODEL, list(retry_feedback), repo_root=repo_root, llm_backend=backend
    )
    assert call_count(log_path) == 1
    assert field(second, "cache_hit") is True
    assert field(second, "files") == files
    assert field(second, "model_call_error") is None
    assert field(second, "refused") is None


def test_commit_cache_writes_nothing_for_model_call_error(env):
    cache_manager = load_cache_manager()
    repo_root = make_repo(env / "repo_err")
    log_path = env / "model_calls_err.log"
    bundle = make_bundle("ac-gen-006-error")
    key = make_key(cache_manager, bundle, None, MODEL)

    result = generator.generate(
        bundle, MODEL, None, repo_root=repo_root, llm_backend=make_backend(log_path, fail=True)
    )
    assert field(result, "model_call_error") is not None
    assert field(result, "files") == {}
    assert field(result, "cache_hit") is False

    generator.commit_cache(result, repo_root)

    assert is_miss(cache_manager, cache_manager.get(key, repo_root=repo_root))
    assert field(cache_manager.stats(repo_root=repo_root), "entry_count") == 0