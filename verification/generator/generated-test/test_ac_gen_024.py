# hotdocs-criterion: sha256:6154ba70ad220054ffc46ee13dc0113ad6cd4770ae22e9897898ac76baa8e7cd
import importlib.util
import re
import sys
from pathlib import Path

import pytest

import generator


FAKE_KIND_ADAPTER = '''from pathlib import Path

KIND = "fake"


def layout_errors(asset_file):
    return ["bad"] if "bad" in Path(asset_file).read_text(encoding="utf-8") else []


def provision(repo_root):
    if (Path(repo_root) / "NO_ENV").exists():
        return {"ok": False, "reason": "fake needs fakeprog >= 2", "versions": {}, "lockfile_sha256": None}
    return {"ok": True, "reason": "", "versions": {"fakeprog": "2.0.0"}, "lockfile_sha256": None}
'''

FAKE_PYTHON_ADAPTER = '''from pathlib import Path

KIND = "python"


def layout_errors(code_dir):
    return ["bad.py:1: SyntaxError: x"] if (Path(code_dir) / "bad.py").exists() else []


def provision(repo_root):
    return {"ok": True, "reason": "", "versions": {"python": "3.12"}, "lockfile_sha256": None, "interpreter": "/fake/python"}
'''

SECTIONS = [
    "Layout",
    "Environment",
    "Surface",
    "Running criteria",
    "Strength check",
    "Test author guidance",
    "Generator guidance",
]


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


def make_repo(repo_root, kind="fake"):
    comp_dir = repo_root / "specs" / "components" / "widget-maker"
    comp_dir.mkdir(parents=True)
    component_md = (
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
        "# Widget Maker\n"
    )
    (comp_dir / "component.md").write_text(component_md, encoding="utf-8")

    arch = repo_root / "specs" / "architecture"
    arch.mkdir(parents=True)
    definition = "# Fake\n"
    for s in SECTIONS:
        definition += "\n## " + s + "\nx\n"
    (arch / "asset-kind-fake.md").write_text(definition, encoding="utf-8")

    fake_dir = repo_root / "gen" / "kind-fake"
    fake_dir.mkdir(parents=True)
    (fake_dir / "kind_fake.py").write_text(FAKE_KIND_ADAPTER, encoding="utf-8")

    py_dir = repo_root / "gen" / "kind-python"
    py_dir.mkdir(parents=True)
    (py_dir / "kind_python.py").write_text(FAKE_PYTHON_ADAPTER, encoding="utf-8")


def make_bundle(tag):
    return {
        "component_id": "comp-widget-maker",
        "spec_bundle_hash": "sha256:" + ("%064x" % tag),
        "spec": "Widget Maker spec",
        "interface": "Widget Maker interface",
        "constraints": "",
        "dependency_interfaces": {},
        "dependency_context": {},
        "dependency_usage": {},
        "vars": {},
        "glossary": "",
        "hint_code": None,
    }


def make_backend(blocks):
    def backend(prompt, model, **params):
        nonce = re.search(r"-----BEGIN FILE ([0-9a-f]{32}):", prompt).group(1)
        text = ""
        for path, content in blocks:
            text += "-----BEGIN FILE " + nonce + ": " + path + "-----\n"
            text += content
            text += "-----END FILE " + nonce + "-----\n"
        text += "-----END REPLY " + nonce + "-----\n"
        return {"text": text, "model": model, "backend": "mock", "model_call_error": None}

    return backend


def assert_nothing_cached(repo_root):
    cache_manager = load_cache_manager()
    stats = cache_manager.stats(repo_root=repo_root)
    assert field(stats, "entry_count") == 0


@pytest.fixture(autouse=True)
def _no_cache_store(monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)


def test_missing_asset(tmp_path):
    repo_root = tmp_path / "repo"
    make_repo(repo_root)
    backend = make_backend([("widget_maker.py", "A = 1\n")])
    result = generator.generate(
        make_bundle(1), "claude-sonnet-5", repo_root=repo_root, llm_backend=backend
    )
    assert field(result, "model_call_error") == {
        "category": "missing_asset",
        "message": "missing asset: static/app.txt",
    }
    assert field(result, "files") == {}
    assert not (repo_root / "gen" / "widget-maker").exists()
    assert_nothing_cached(repo_root)


def test_asset_layout_error(tmp_path):
    repo_root = tmp_path / "repo"
    make_repo(repo_root)
    backend = make_backend([
        ("widget_maker.py", "A = 1\n"),
        ("static/app.txt", "bad\n"),
    ])
    result = generator.generate(
        make_bundle(2), "claude-sonnet-5", repo_root=repo_root, llm_backend=backend
    )
    assert field(result, "model_call_error") == {
        "category": "malformed_layout",
        "message": "static/app.txt: bad",
    }
    assert field(result, "files") == {}
    assert not (repo_root / "gen" / "widget-maker").exists()
    assert_nothing_cached(repo_root)


def test_valid_asset_with_prefix_written(tmp_path):
    repo_root = tmp_path / "repo"
    make_repo(repo_root)
    backend = make_backend([
        ("widget_maker.py", "A = 1\n"),
        ("widget-maker/static/app.txt", "ok\n"),
    ])
    result = generator.generate(
        make_bundle(3), "claude-sonnet-5", repo_root=repo_root, llm_backend=backend
    )
    assert field(result, "model_call_error") is None
    assert field(result, "files") == {
        "widget_maker.py": "A = 1\n",
        "static/app.txt": "ok\n",
    }
    asset = repo_root / "gen" / "widget-maker" / "static" / "app.txt"
    assert asset.is_file()
    assert asset.read_text(encoding="utf-8") == "ok\n"


def test_unknown_asset_kind(tmp_path):
    repo_root = tmp_path / "repo"
    make_repo(repo_root, kind="nosuchkind")
    backend = make_backend([
        ("widget_maker.py", "A = 1\n"),
        ("static/app.txt", "ok\n"),
    ])
    result = generator.generate(
        make_bundle(4), "claude-sonnet-5", repo_root=repo_root, llm_backend=backend
    )
    assert field(result, "model_call_error") == {
        "category": "environment",
        "message": "unknown asset kind: nosuchkind",
    }
    assert field(result, "files") == {}
    assert not (repo_root / "gen" / "widget-maker").exists()
    assert_nothing_cached(repo_root)