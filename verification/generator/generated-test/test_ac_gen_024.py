# hotdocs-criterion: sha256:e8772c24e450f46a5b8900d47c8d7d9fe3abd0949e145a8aa474b04320c5d427
import importlib.util
import re
import sys
from pathlib import Path

import pytest

import generator


MODEL = "claude-sonnet-5"
COMPONENT_ID = "comp-widget-maker"

SECTIONS = [
    "Layout",
    "Environment",
    "Surface",
    "Running criteria",
    "Strength check",
    "Test author guidance",
    "Generator guidance",
]

FAKE_ADAPTER = '''from pathlib import Path

KIND = "fake"


def layout_errors(asset_file):
    return ["bad"] if "bad" in Path(asset_file).read_text(encoding="utf-8") else []


def provision(repo_root):
    if (Path(repo_root) / "NO_ENV").exists():
        return {"ok": False, "reason": "fake needs fakeprog >= 2", "versions": {}, "lockfile_sha256": None}
    return {"ok": True, "reason": "", "versions": {"fakeprog": "2.0.0"}, "lockfile_sha256": None}
'''

PYTHON_ADAPTER = '''from pathlib import Path

KIND = "python"


def layout_errors(code_dir):
    return ["bad.py:1: SyntaxError: x"] if (Path(code_dir) / "bad.py").exists() else []


def provision(repo_root):
    return {"ok": True, "reason": "", "versions": {"python": "3.12"}, "lockfile_sha256": None, "interpreter": "/fake/python"}
'''


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
    path = base / "cache_manager.py" if (base / "cache_manager.py").is_file() else base / "cache_manager" / "__init__.py"
    return load_module(path, "cache_manager")


class Bundle:
    def __init__(self):
        self.component_id = COMPONENT_ID
        self.spec_bundle_hash = "sha256:" + "a" * 64
        self.spec = "# Widget Maker\n\nMakes widgets."
        self.interface = "widget_maker module"
        self.constraints = ""
        self.dependency_interfaces = {}
        self.dependency_context = {}
        self.dependency_usage = {}
        self.vars = {}
        self.glossary = ""
        self.hint_code = None
        self.spec_bundle_parts = {}

    def __getitem__(self, key):
        return getattr(self, key)

    def get(self, key, default=None):
        return getattr(self, key, default)

    def keys(self):
        return list(vars(self).keys())


def plant_repo(repo_root, kind="fake"):
    comp_dir = repo_root / "specs" / "components" / "widget-maker"
    comp_dir.mkdir(parents=True)
    (comp_dir / "component.md").write_text(
        "---\n"
        "id: comp-widget-maker\n"
        "title: Widget Maker\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "depends_on: []\n"
        "sealed: false\n"
        "assets: [" + kind + ":static/app.txt]\n"
        "---\n"
        "\n"
        "# Widget Maker\n",
        encoding="utf-8",
    )
    arch = repo_root / "specs" / "architecture"
    arch.mkdir(parents=True)
    definition = "# Fake\n"
    for name in SECTIONS:
        definition += "\n## " + name + "\n\nx\n"
    (arch / "asset-kind-fake.md").write_text(definition, encoding="utf-8")
    fake_dir = repo_root / "gen" / "kind-fake"
    fake_dir.mkdir(parents=True)
    (fake_dir / "kind_fake.py").write_text(FAKE_ADAPTER, encoding="utf-8")
    py_dir = repo_root / "gen" / "kind-python"
    py_dir.mkdir(parents=True)
    (py_dir / "kind_python.py").write_text(PYTHON_ADAPTER, encoding="utf-8")


def make_backend(blocks):
    def backend(prompt, model, **params):
        nonce = re.search(r"-----BEGIN FILE ([0-9a-f]{32}):", prompt).group(1)
        text = "Here are the files.\n"
        for path, content in blocks:
            text += "-----BEGIN FILE " + nonce + ": " + path + "-----\n"
            text += content + "\n"
            text += "-----END FILE " + nonce + "-----\n"
        text += "-----END REPLY " + nonce + "-----\n"
        return {"text": text, "model": model, "backend": "mock", "model_call_error": None}

    return backend


@pytest.fixture
def repo_root(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    root = tmp_path / "repo"
    root.mkdir()
    monkeypatch.chdir(root)
    return root


def run(repo_root, blocks):
    return generator.generate(Bundle(), MODEL, repo_root=repo_root, llm_backend=make_backend(blocks))


def assert_nothing_written_or_cached(repo_root):
    assert not (repo_root / "gen" / "widget-maker").exists()
    cache_manager = load_cache_manager()
    assert cache_manager.stats(repo_root=repo_root)["entry_count"] == 0


def test_missing_declared_asset(repo_root):
    plant_repo(repo_root)
    result = run(repo_root, [("widget_maker.py", "A = 1")])
    assert field(result, "model_call_error") == {
        "category": "missing_asset",
        "message": "missing asset: static/app.txt",
    }
    assert field(result, "files") == {}
    assert_nothing_written_or_cached(repo_root)


def test_asset_layout_error(repo_root):
    plant_repo(repo_root)
    result = run(repo_root, [("widget_maker.py", "A = 1"), ("static/app.txt", "bad")])
    assert field(result, "model_call_error") == {
        "category": "malformed_layout",
        "message": "static/app.txt: bad",
    }
    assert field(result, "files") == {}
    assert_nothing_written_or_cached(repo_root)


def test_valid_asset_written(repo_root):
    plant_repo(repo_root)
    result = run(
        repo_root,
        [("widget_maker.py", "A = 1"), ("widget-maker/static/app.txt", "ok")],
    )
    assert field(result, "model_call_error") is None
    assert field(result, "files") == {"widget_maker.py": "A = 1\n", "static/app.txt": "ok\n"}
    written = repo_root / "gen" / "widget-maker" / "static" / "app.txt"
    assert written.read_text(encoding="utf-8") == "ok\n"


def test_unknown_asset_kind(repo_root):
    plant_repo(repo_root, kind="nosuchkind")
    result = run(repo_root, [("widget_maker.py", "A = 1"), ("static/app.txt", "ok")])
    assert field(result, "model_call_error") == {
        "category": "environment",
        "message": "unknown asset kind: nosuchkind",
    }
    assert field(result, "files") == {}
    assert_nothing_written_or_cached(repo_root)