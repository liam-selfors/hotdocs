# hotdocs-criterion: sha256:61d6c0f6bc002159788d5e6062efc9dfd31c8d5f49dd30371ad00cbe945d4c2e
import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest

import generator


COMPONENT_ID = "comp-widget-maker"
SLUG = "widget-maker"
MODEL = "claude-sonnet-5"
HINT_FILE = "widget_maker.py"
HINT_CONTENT = "def old():\n    return 0\n"
FRESH_CONTENT = "def make_widget():\n    return 'fresh'\n"
CACHED_CONTENT = "def make_widget():\n    return 'cached'\n"

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


def snapshot(directory):
    directory = Path(directory)
    if not directory.exists():
        return None
    return {
        str(p.relative_to(directory)): p.read_bytes()
        for p in sorted(directory.rglob("*"))
        if p.is_file()
    }


def make_repo(tmp_path):
    repo_root = tmp_path / "repo"
    adapter = repo_root / "gen" / "kind-python" / "kind_python.py"
    adapter.parent.mkdir(parents=True)
    adapter.write_text(PYTHON_ADAPTER, encoding="utf-8")
    comp_dir = repo_root / "gen" / SLUG
    comp_dir.mkdir(parents=True)
    (comp_dir / HINT_FILE).write_text(HINT_CONTENT, encoding="utf-8")
    return repo_root, comp_dir


def make_bundle(spec_bundle_hash):
    return {
        "component_id": COMPONENT_ID,
        "spec_bundle_hash": spec_bundle_hash,
        "spec": "# Widget Maker\n\nMakes widgets.",
        "interface": "make_widget() -> str",
        "constraints": "",
        "dependency_interfaces": {},
        "dependency_context": {},
        "dependency_usage": {},
        "vars": {},
        "glossary": "",
        "hint_code": {HINT_FILE: HINT_CONTENT},
    }


def make_backend(log_path, content):
    def backend(prompt, model, **params):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write("call\n")
        nonce = re.search(r"-----BEGIN FILE ([0-9a-f]{32}):", prompt).group(1)
        text = (
            "-----BEGIN FILE " + nonce + ": " + HINT_FILE + "-----\n"
            + content
            + "-----END FILE " + nonce + "-----\n"
            + "-----END REPLY " + nonce + "-----\n"
        )
        return {"text": text, "model": model, "backend": "mock", "model_call_error": None}

    return backend


def calls(log_path):
    log_path = Path(log_path)
    if not log_path.exists():
        return 0
    return len([l for l in log_path.read_text(encoding="utf-8").splitlines() if l.strip()])


def make_key(cache_manager, spec_bundle_hash):
    gate_inputs_hash = "sha256:" + hashlib.sha256(
        json.dumps(sorted([]), sort_keys=True).encode("utf-8")
    ).hexdigest()
    return cache_manager.CacheKey(
        spec_bundle_hash=spec_bundle_hash,
        gate_inputs_hash=gate_inputs_hash,
        gate_version=generator.GATE_VERSION,
        model_pin=MODEL,
    )


@pytest.fixture(autouse=True)
def _env(monkeypatch, tmp_path):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    work = tmp_path / "cwd"
    work.mkdir()
    monkeypatch.chdir(work)


def test_hint_mode_miss_returns_candidate_without_writing_gen_or_cache(tmp_path):
    repo_root, comp_dir = make_repo(tmp_path)
    cache_manager = load_cache_manager()
    spec_bundle_hash = "sha256:" + hashlib.sha256(b"hint-miss-bundle").hexdigest()
    bundle = make_bundle(spec_bundle_hash)
    key = make_key(cache_manager, spec_bundle_hash)

    assert isinstance(cache_manager.get(key, repo_root=repo_root), cache_manager.Miss)
    entries_before = cache_manager.stats(repo_root=repo_root)["entry_count"]

    log_path = tmp_path / "model_calls.log"
    before = snapshot(comp_dir)

    result = generator.generate(
        bundle, MODEL, repo_root=repo_root, llm_backend=make_backend(log_path, FRESH_CONTENT)
    )

    assert calls(log_path) == 1
    assert field(result, "model_call_error") is None
    assert field(result, "refused") is None
    assert field(result, "cache_hit") is False
    assert field(result, "files") == {HINT_FILE: FRESH_CONTENT}

    assert snapshot(comp_dir) == before
    assert isinstance(cache_manager.get(key, repo_root=repo_root), cache_manager.Miss)
    assert cache_manager.stats(repo_root=repo_root)["entry_count"] == entries_before

    generator.commit_cache(result, repo_root=repo_root)

    assert isinstance(cache_manager.get(key, repo_root=repo_root), cache_manager.Miss)
    assert cache_manager.stats(repo_root=repo_root)["entry_count"] == entries_before
    assert snapshot(comp_dir) == before


def test_hint_mode_cache_hit_returns_cached_without_model_call_or_gen_write(tmp_path):
    repo_root, comp_dir = make_repo(tmp_path)
    cache_manager = load_cache_manager()
    spec_bundle_hash = "sha256:" + hashlib.sha256(b"hint-hit-bundle").hexdigest()
    bundle = make_bundle(spec_bundle_hash)
    key = make_key(cache_manager, spec_bundle_hash)

    payload = {
        "component_id": COMPONENT_ID,
        "spec_bundle_hash": spec_bundle_hash,
        "model": MODEL,
        "prompt_version": getattr(generator, "PROMPT_VERSION", "v12"),
        "cache_hit": False,
        "files": {HINT_FILE: CACHED_CONTENT},
        "model_call_error": None,
        "refused": None,
        "retry_feedback": None,
        "mode": "single",
        "transcript_sha256": None,
        "turns": 1,
        "tool_calls": 0,
        "isolation": None,
    }
    cache_manager.put(
        key,
        cache_manager.CachedResult(
            gate_type="generator", payload=payload, stored_at=cache_manager.now_iso()
        ),
        repo_root=repo_root,
    )
    assert not isinstance(cache_manager.get(key, repo_root=repo_root), cache_manager.Miss)

    log_path = tmp_path / "model_calls.log"
    before = snapshot(comp_dir)

    result = generator.generate(
        bundle, MODEL, repo_root=repo_root, llm_backend=make_backend(log_path, FRESH_CONTENT)
    )

    assert calls(log_path) == 0
    assert field(result, "cache_hit") is True
    assert field(result, "files") == {HINT_FILE: CACHED_CONTENT}
    assert field(result, "model_call_error") is None
    assert field(result, "refused") is None
    assert snapshot(comp_dir) == before