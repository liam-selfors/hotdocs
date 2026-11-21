# hotdocs-criterion: sha256:26532f687c72f0c78dab45ca1d1c4f2f4f78a46435b077b4892e9fc712304df0
import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest

import generator


MODEL = "mock-model"
COMPONENT_ID = "comp-widget-maker"
SLUG = "widget-maker"
BUNDLE_HASH = "sha256:" + "a" * 64
HINT_FILES = {"widget_maker.py": "def make():\n    return 1\n"}
NEW_FILES = {"widget_maker.py": "def make():\n    return 2\n"}
CACHED_FILES = {"widget_maker.py": "def make():\n    return 3\n"}


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


def make_bundle(hint_code):
    return Bundle(
        component_id=COMPONENT_ID,
        spec_bundle_hash=BUNDLE_HASH,
        spec="# Widget Maker\n\nMakes widgets.",
        interface="make() -> int",
        constraints="None.",
        dependency_interfaces={},
        dependency_context={},
        dependency_usage={},
        vars={},
        glossary="",
        hint_code=hint_code,
    )


PYTHON_ADAPTER = (
    "from pathlib import Path\n"
    "\n"
    "KIND = " + repr("python") + "\n"
    "\n"
    "\n"
    "def layout_errors(code_dir):\n"
    "    return [" + repr("bad.py:1: SyntaxError: x") + "] if (Path(code_dir) / " + repr("bad.py") + ").exists() else []\n"
    "\n"
    "\n"
    "def provision(repo_root):\n"
    "    return {" + repr("ok") + ": True, " + repr("reason") + ": " + repr("") + ", "
    + repr("versions") + ": {" + repr("python") + ": " + repr("3.12") + "}, "
    + repr("lockfile_sha256") + ": None, " + repr("interpreter") + ": " + repr("/fake/python") + "}\n"
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


@pytest.fixture
def repo_root(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    root = tmp_path / "repo"
    comp_dir = root / "specs" / "components" / SLUG
    comp_dir.mkdir(parents=True)
    (comp_dir / "component.md").write_text(COMPONENT_MD, encoding="utf-8")
    adapter_dir = root / "gen" / "kind-python"
    adapter_dir.mkdir(parents=True)
    (adapter_dir / "kind_python.py").write_text(PYTHON_ADAPTER, encoding="utf-8")
    code_dir = root / "gen" / SLUG
    code_dir.mkdir(parents=True)
    for rel, content in HINT_FILES.items():
        (code_dir / rel).write_text(content, encoding="utf-8")
    monkeypatch.chdir(root)
    return root


def snapshot(repo_root):
    code_dir = repo_root / "gen" / SLUG
    if not code_dir.exists():
        return None
    return {
        str(p.relative_to(code_dir)): p.read_bytes()
        for p in sorted(code_dir.rglob("*"))
        if p.is_file()
    }


def make_backend(log_path, files):
    def backend(prompt, model, **params):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write("call\n")
        nonce = re.search(r"-----BEGIN FILE ([0-9a-f]{32}):", prompt).group(1)
        text = ""
        for rel, content in files.items():
            text += "-----BEGIN FILE " + nonce + ": " + rel + "-----\n"
            text += content
            text += "-----END FILE " + nonce + "-----\n"
        text += "-----END REPLY " + nonce + "-----\n"
        return {"text": text, "model": model, "backend": "mock", "model_call_error": None}

    return backend


def calls(log_path):
    if not log_path.exists():
        return 0
    return len([l for l in log_path.read_text(encoding="utf-8").splitlines() if l.strip()])


def normalize(files):
    prefix = "gen/" + SLUG + "/"
    return {(k[len(prefix):] if k.startswith(prefix) else k): v for k, v in dict(files).items()}


def cache_key(cache_manager):
    digest = hashlib.sha256(json.dumps(sorted([]), sort_keys=True).encode("utf-8")).hexdigest()
    return cache_manager.CacheKey(
        spec_bundle_hash=BUNDLE_HASH,
        gate_inputs_hash="sha256:" + digest,
        gate_version=generator.GATE_VERSION,
        model_pin=MODEL,
    )


def test_hint_mode_miss_writes_nothing(repo_root, tmp_path):
    cache_manager = load_cache_manager()
    log_path = tmp_path / "model_calls.log"
    before = snapshot(repo_root)

    result = generator.generate(
        make_bundle(dict(HINT_FILES)),
        MODEL,
        repo_root=repo_root,
        llm_backend=make_backend(log_path, NEW_FILES),
    )

    assert calls(log_path) == 1
    assert field(result, "model_call_error") is None
    assert field(result, "refused") is None
    assert field(result, "cache_hit") is False
    assert normalize(field(result, "files")) == NEW_FILES

    assert snapshot(repo_root) == before

    generator.commit_cache(result, repo_root=repo_root)

    assert snapshot(repo_root) == before
    hit = cache_manager.get(cache_key(cache_manager), repo_root=repo_root)
    assert isinstance(hit, cache_manager.Miss)
    assert field(cache_manager.stats(repo_root=repo_root), "entry_count") == 0


def test_hint_mode_cache_hit_returns_cached_without_model_call(repo_root, tmp_path):
    cache_manager = load_cache_manager()
    key = cache_key(cache_manager)

    if hasattr(generator, "GenerationResult"):
        cold = generator.GenerationResult(
            component_id=COMPONENT_ID,
            spec_bundle_hash=BUNDLE_HASH,
            model=MODEL,
            prompt_version=generator.PROMPT_VERSION,
            cache_hit=False,
            files=dict(CACHED_FILES),
            model_call_error=None,
            refused=None,
            retry_feedback=None,
            mode="single",
            transcript_sha256=None,
            turns=1,
            tool_calls=0,
            isolation=None,
        )
        generator.commit_cache(cold, repo_root=repo_root)
    else:
        cache_manager.put(
            key,
            cache_manager.CachedResult(
                gate_type="generator",
                payload={
                    "component_id": COMPONENT_ID,
                    "model": MODEL,
                    "prompt_version": generator.PROMPT_VERSION,
                    "files": dict(CACHED_FILES),
                },
                stored_at=cache_manager.now_iso(),
            ),
            repo_root=repo_root,
        )

    assert not isinstance(cache_manager.get(key, repo_root=repo_root), cache_manager.Miss)

    log_path = tmp_path / "model_calls.log"
    before = snapshot(repo_root)

    result = generator.generate(
        make_bundle(dict(HINT_FILES)),
        MODEL,
        repo_root=repo_root,
        llm_backend=make_backend(log_path, NEW_FILES),
    )

    assert calls(log_path) == 0
    assert field(result, "cache_hit") is True
    assert field(result, "model_call_error") is None
    assert field(result, "refused") is None
    assert normalize(field(result, "files")) == CACHED_FILES
    assert snapshot(repo_root) == before