# hotdocs-criterion: sha256:758f217f863894745e21e97e0ebb2d21387c1eff7d1aec1c1e8c657f093c2225
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
MODEL = "mock-model"

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


class Bundle:
    """A SpecBundle-shaped object readable by attribute and as a mapping."""

    _FIELDS = (
        "component_id", "spec_bundle_hash", "spec", "interface", "constraints",
        "dependency_interfaces", "dependency_context", "dependency_usage",
        "vars", "glossary", "hint_code", "spec_bundle_parts",
    )

    def __init__(self, **kwargs):
        for name in self._FIELDS:
            setattr(self, name, kwargs.get(name))

    def __getitem__(self, key):
        if key not in self._FIELDS:
            raise KeyError(key)
        return getattr(self, key)

    def get(self, key, default=None):
        return getattr(self, key) if key in self._FIELDS else default

    def keys(self):
        return list(self._FIELDS)

    def __iter__(self):
        return iter(self._FIELDS)

    def __len__(self):
        return len(self._FIELDS)

    def __contains__(self, key):
        return key in self._FIELDS


SPEC_HASH = "sha256:" + "ab" * 32


def make_bundle(hint_code):
    return Bundle(
        component_id=COMPONENT_ID,
        spec_bundle_hash=SPEC_HASH,
        spec="# Widget Maker\n\nMakes widgets.",
        interface="make() -> int",
        constraints="",
        dependency_interfaces={},
        dependency_context={},
        dependency_usage={},
        vars={},
        glossary="",
        hint_code=hint_code,
        spec_bundle_parts={"spec": SPEC_HASH, "dependency_code": "sha256:" + "cd" * 32},
    )


def make_mock(log_path, files):
    def backend(prompt, model, **params):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write("call\n")
        nonce = re.search(r"-----BEGIN FILE ([0-9a-f]{32}):", prompt).group(1)
        text = ""
        for path in sorted(files):
            text += "-----BEGIN FILE " + nonce + ": " + path + "-----\n"
            text += files[path]
            text += "-----END FILE " + nonce + "-----\n"
        text += "-----END REPLY " + nonce + "-----\n"
        return {"text": text, "model": model, "backend": "mock", "model_call_error": None}

    return backend


def call_count(log_path):
    if not log_path.exists():
        return 0
    return len([l for l in log_path.read_text(encoding="utf-8").splitlines() if l.strip()])


def snapshot(directory):
    if not directory.exists():
        return None
    return {
        str(p.relative_to(directory)): p.read_bytes()
        for p in sorted(directory.rglob("*"))
        if p.is_file()
    }


def cache_key(cm):
    gate_inputs_hash = "sha256:" + hashlib.sha256(
        json.dumps(sorted([]), sort_keys=True).encode("utf-8")
    ).hexdigest()
    return cm.CacheKey(
        spec_bundle_hash=SPEC_HASH,
        gate_inputs_hash=gate_inputs_hash,
        gate_version=generator.GATE_VERSION,
        model_pin=MODEL,
    )


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    adapter = repo_root / "gen" / "kind-python" / "kind_python.py"
    adapter.parent.mkdir(parents=True)
    adapter.write_text(FAKE_PYTHON_ADAPTER, encoding="utf-8")
    comp = repo_root / "specs" / "components" / SLUG / "component.md"
    comp.parent.mkdir(parents=True)
    comp.write_text(COMPONENT_MD, encoding="utf-8")
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    monkeypatch.chdir(tmp_path)
    return repo_root, log_dir


OLD_FILES = {"widget_maker.py": "def make():\n    return 0\n"}
NEW_FILES = {"widget_maker.py": "def make():\n    return 1\n"}


def plant_existing_gen(repo_root):
    gen_dir = repo_root / "gen" / SLUG
    gen_dir.mkdir(parents=True, exist_ok=True)
    for path, content in OLD_FILES.items():
        (gen_dir / path).write_text(content, encoding="utf-8")
    return gen_dir


def test_hint_mode_miss_returns_candidate_without_writing(env):
    repo_root, log_dir = env
    cm = load_cache_manager()
    gen_dir = plant_existing_gen(repo_root)
    before = snapshot(gen_dir)
    log_path = log_dir / "hint_calls.txt"

    assert isinstance(cm.get(cache_key(cm), repo_root=repo_root), cm.Miss)

    bundle = make_bundle(dict(OLD_FILES))
    result = generator.generate(
        bundle, MODEL, repo_root=repo_root, llm_backend=make_mock(log_path, NEW_FILES)
    )

    assert call_count(log_path) == 1
    assert field(result, "model_call_error") is None
    assert field(result, "refused") is None
    assert field(result, "cache_hit") is False
    files = field(result, "files")
    assert files == NEW_FILES

    # gen/<component>/ untouched
    assert snapshot(gen_dir) == before
    # nothing written to the cache
    assert isinstance(cm.get(cache_key(cm), repo_root=repo_root), cm.Miss)
    assert field(cm.stats(repo_root=repo_root), "entry_count") == 0


def test_hint_mode_hit_returns_cached_cold_result_without_model_call(env):
    repo_root, log_dir = env
    cm = load_cache_manager()

    # Produce and commit a cold-mode result for this exact spec state.
    cold_log = log_dir / "cold_calls.txt"
    cold = generator.generate(
        make_bundle(None), MODEL, repo_root=repo_root, llm_backend=make_mock(cold_log, NEW_FILES)
    )
    assert call_count(cold_log) == 1
    assert field(cold, "files") == NEW_FILES
    generator.commit_cache(cold, repo_root=repo_root)
    assert not isinstance(cm.get(cache_key(cm), repo_root=repo_root), cm.Miss)
    entries_before = field(cm.stats(repo_root=repo_root), "entry_count")

    # Make gen/<component>/ distinct from the cached files, then snapshot it.
    gen_dir = plant_existing_gen(repo_root)
    before = snapshot(gen_dir)

    hint_log = log_dir / "hint_calls.txt"
    other_files = {"widget_maker.py": "def make():\n    return 2\n"}
    result = generator.generate(
        make_bundle(dict(OLD_FILES)), MODEL, repo_root=repo_root,
        llm_backend=make_mock(hint_log, other_files),
    )

    assert call_count(hint_log) == 0
    assert field(result, "cache_hit") is True
    assert field(result, "model_call_error") is None
    assert field(result, "refused") is None
    assert field(result, "files") == NEW_FILES

    assert snapshot(gen_dir) == before
    assert field(cm.stats(repo_root=repo_root), "entry_count") == entries_before