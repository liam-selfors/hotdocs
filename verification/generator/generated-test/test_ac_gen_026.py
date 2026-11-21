# hotdocs-criterion: sha256:df060afc53ebb2726fe2725025937b77758f250f4eaa5367931ae727c5d70636
from pathlib import Path

import generator


SECTIONS = [
    "Layout",
    "Environment",
    "Surface",
    "Running criteria",
    "Strength check",
    "Test author guidance",
    "Generator guidance",
]


def _python_adapter_source(log_path):
    return (
        "from pathlib import Path\n"
        "\n"
        'KIND = "python"\n'
        "LOG = " + repr(str(log_path)) + "\n"
        "\n"
        "\n"
        "def layout_errors(code_dir):\n"
        '    return ["bad.py:1: SyntaxError: x"] if (Path(code_dir) / "bad.py").exists() else []\n'
        "\n"
        "\n"
        "def provision(repo_root):\n"
        '    with open(LOG, "a", encoding="utf-8") as f:\n'
        '        f.write("python\\n")\n'
        '    return {"ok": True, "reason": "", "versions": {"python": "3.12"}, "lockfile_sha256": None, "interpreter": "/fake/python"}\n'
    )


def _fake_adapter_source(log_path):
    return (
        "from pathlib import Path\n"
        "\n"
        'KIND = "fake"\n'
        "LOG = " + repr(str(log_path)) + "\n"
        "\n"
        "\n"
        "def layout_errors(asset_file):\n"
        '    return ["bad"] if "bad" in Path(asset_file).read_text(encoding="utf-8") else []\n'
        "\n"
        "\n"
        "def provision(repo_root):\n"
        '    with open(LOG, "a", encoding="utf-8") as f:\n'
        '        f.write("fake\\n")\n'
        '    if (Path(repo_root) / "NO_ENV").exists():\n'
        '        return {"ok": False, "reason": "fake needs fakeprog >= 2", "versions": {}, "lockfile_sha256": None}\n'
        '    return {"ok": True, "reason": "", "versions": {"fakeprog": "2.0.0"}, "lockfile_sha256": None}\n'
    )


def _component_md(kind):
    return (
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


def make_repo(tmp_path, kind="fake", component=True):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "provision_calls.log"

    py_dir = repo_root / "gen" / "kind-python"
    py_dir.mkdir(parents=True)
    (py_dir / "kind_python.py").write_text(_python_adapter_source(log_path), encoding="utf-8")

    if component:
        comp_dir = repo_root / "specs" / "components" / "widget-maker"
        comp_dir.mkdir(parents=True)
        (comp_dir / "component.md").write_text(_component_md(kind), encoding="utf-8")

        arch = repo_root / "specs" / "architecture"
        arch.mkdir(parents=True)
        definition = "# Fake\n"
        for name in SECTIONS:
            definition += "\n## " + name + "\n\nx\n"
        (arch / "asset-kind-fake.md").write_text(definition, encoding="utf-8")

        fake_dir = repo_root / "gen" / "kind-fake"
        fake_dir.mkdir(parents=True)
        (fake_dir / "kind_fake.py").write_text(_fake_adapter_source(log_path), encoding="utf-8")

    return repo_root, log_path


def snapshot(repo_root):
    return {
        str(p.relative_to(repo_root))
        for p in repo_root.rglob("*")
        if "__pycache__" not in p.parts
    }


def norm(result):
    category, messages = result
    return (category, list(messages))


def test_undeclared_files_sorted_and_nothing_written(tmp_path):
    repo_root, _ = make_repo(tmp_path)
    before = snapshot(repo_root)
    result = generator.check_assets(
        "comp-widget-maker",
        {"widget_maker.py": "", "static/app.txt": "ok", "b.md": "", "a.json": ""},
        repo_root=repo_root,
    )
    assert norm(result) == (
        "malformed_layout",
        ["undeclared file: a.json", "undeclared file: b.md"],
    )
    assert snapshot(repo_root) == before
    assert not (repo_root / "gen" / "widget-maker").exists()


def test_package_layout_passes(tmp_path):
    repo_root, _ = make_repo(tmp_path)
    result = generator.check_assets(
        "comp-widget-maker",
        {"widget_maker/__init__.py": "", "static/app.txt": "ok"},
        repo_root=repo_root,
    )
    assert norm(result) == (None, [])


def test_python_layout_errors_and_declared_assets_first(tmp_path):
    repo_root, _ = make_repo(tmp_path)
    result = generator.check_assets(
        "comp-widget-maker",
        {"widget_maker.py": "", "bad.py": "", "static/app.txt": "ok"},
        repo_root=repo_root,
    )
    assert norm(result) == ("malformed_layout", ["bad.py:1: SyntaxError: x"])

    result = generator.check_assets(
        "comp-widget-maker",
        {"widget_maker.py": "", "bad.py": "", "static/app.txt": "bad"},
        repo_root=repo_root,
    )
    assert norm(result) == ("malformed_layout", ["static/app.txt: bad"])


def test_missing_declared_asset(tmp_path):
    repo_root, _ = make_repo(tmp_path)
    result = generator.check_assets(
        "comp-widget-maker",
        {"widget_maker.py": ""},
        repo_root=repo_root,
    )
    assert norm(result) == ("missing_asset", ["missing asset: static/app.txt"])


def test_bare_repo_root_without_component_md(tmp_path):
    repo_root, _ = make_repo(tmp_path, component=False)
    result = generator.check_assets(
        "comp-widget-maker",
        {"widget_maker.py": ""},
        repo_root=repo_root,
    )
    assert norm(result) == (None, [])


def test_check_asset_environment(tmp_path):
    repo_root, log_path = make_repo(tmp_path)

    result = generator.check_asset_environment("comp-widget-maker", repo_root=repo_root)
    assert norm(result) == (None, [])

    (repo_root / "NO_ENV").write_text("", encoding="utf-8")
    if log_path.exists():
        log_path.unlink()

    result = generator.check_asset_environment("comp-widget-maker", repo_root=repo_root)
    assert norm(result) == ("environment", ["fake needs fakeprog >= 2"])

    calls = log_path.read_text(encoding="utf-8").splitlines()
    assert "python" in calls
    assert "fake" in calls
    assert calls.index("python") < calls.index("fake")


def test_check_asset_environment_unknown_kind(tmp_path):
    repo_root, _ = make_repo(tmp_path, kind="nosuchkind")
    result = generator.check_asset_environment("comp-widget-maker", repo_root=repo_root)
    assert norm(result) == ("environment", ["unknown asset kind: nosuchkind"])