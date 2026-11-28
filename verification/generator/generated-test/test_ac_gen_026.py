# hotdocs-criterion: sha256:7f66d92880c9908348f14f3a602c24411c74837892221336a893b417ceea1e5e
from pathlib import Path

import generator


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


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def component_md(kind):
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


def fake_definition():
    text = "# Fake\n"
    for name in SECTIONS:
        text += "\n## " + name + "\n\nx\n"
    return text


def python_adapter_source(log_path):
    src = "from pathlib import Path\n\n"
    src += "KIND = " + repr("python") + "\n\n"
    src += "LOG = " + repr(str(log_path)) + "\n\n\n"
    src += "def layout_errors(code_dir):\n"
    src += "    return [" + repr("bad.py:1: SyntaxError: x") + "] if (Path(code_dir) / " + repr("bad.py") + ").exists() else []\n\n\n"
    src += "def provision(repo_root):\n"
    src += "    with open(LOG, " + repr("a") + ", encoding=" + repr("utf-8") + ") as fh:\n"
    src += "        fh.write(" + repr("python\n") + ")\n"
    src += "    return {" + repr("ok") + ": True, " + repr("reason") + ": " + repr("") + ", "
    src += repr("versions") + ": {" + repr("python") + ": " + repr("3.12") + "}, "
    src += repr("lockfile_sha256") + ": None, " + repr("interpreter") + ": " + repr("/fake/python") + "}\n"
    return src


def fake_adapter_source(log_path):
    src = "from pathlib import Path\n\n"
    src += "KIND = " + repr("fake") + "\n\n"
    src += "LOG = " + repr(str(log_path)) + "\n\n\n"
    src += "def layout_errors(asset_file):\n"
    src += "    return [" + repr("bad") + "] if " + repr("bad") + " in Path(asset_file).read_text(encoding=" + repr("utf-8") + ") else []\n\n\n"
    src += "def provision(repo_root):\n"
    src += "    with open(LOG, " + repr("a") + ", encoding=" + repr("utf-8") + ") as fh:\n"
    src += "        fh.write(" + repr("fake\n") + ")\n"
    src += "    if (Path(repo_root) / " + repr("NO_ENV") + ").exists():\n"
    src += "        return {" + repr("ok") + ": False, " + repr("reason") + ": " + repr("fake needs fakeprog >= 2") + ", "
    src += repr("versions") + ": {}, " + repr("lockfile_sha256") + ": None}\n"
    src += "    return {" + repr("ok") + ": True, " + repr("reason") + ": " + repr("") + ", "
    src += repr("versions") + ": {" + repr("fakeprog") + ": " + repr("2.0.0") + "}, "
    src += repr("lockfile_sha256") + ": None}\n"
    return src


def make_repo(tmp_path, name="repo", kind="fake", with_component=True):
    repo_root = tmp_path / name
    repo_root.mkdir()
    log_path = tmp_path / (name + "-provision.log")

    py_dir = repo_root / "gen" / "kind-python"
    py_dir.mkdir(parents=True)
    (py_dir / "kind_python.py").write_text(python_adapter_source(log_path), encoding="utf-8")

    if with_component:
        comp_dir = repo_root / "specs" / "components" / "widget-maker"
        comp_dir.mkdir(parents=True)
        (comp_dir / "component.md").write_text(component_md(kind), encoding="utf-8")

        if kind == "fake":
            arch = repo_root / "specs" / "architecture"
            arch.mkdir(parents=True)
            (arch / "asset-kind-fake.md").write_text(fake_definition(), encoding="utf-8")
            fake_dir = repo_root / "gen" / "kind-fake"
            fake_dir.mkdir(parents=True)
            (fake_dir / "kind_fake.py").write_text(fake_adapter_source(log_path), encoding="utf-8")

    return repo_root, log_path


def snapshot(root):
    return sorted(
        str(p.relative_to(root))
        for p in root.rglob("*")
        if "__pycache__" not in p.parts
    )


def normalize(result):
    category, messages = result
    return (category, list(messages))


def read_log(log_path):
    if not log_path.exists():
        return []
    return [line for line in log_path.read_text(encoding="utf-8").split("\n") if line]


def test_undeclared_files_are_malformed_layout_and_nothing_written(tmp_path):
    repo_root, _ = make_repo(tmp_path)
    before = snapshot(repo_root)
    files = {"widget_maker.py": "", "static/app.txt": "ok", "b.md": "", "a.json": ""}
    result = generator.check_assets(COMPONENT_ID, files, repo_root=repo_root)
    assert normalize(result) == (
        "malformed_layout",
        ["undeclared file: a.json", "undeclared file: b.md"],
    )
    assert snapshot(repo_root) == before


def test_package_module_with_declared_asset_passes(tmp_path):
    repo_root, _ = make_repo(tmp_path)
    before = snapshot(repo_root)
    files = {"widget_maker/__init__.py": "", "static/app.txt": "ok"}
    result = generator.check_assets(COMPONENT_ID, files, repo_root=repo_root)
    assert normalize(result) == (None, [])
    assert snapshot(repo_root) == before


def test_python_layout_errors_and_asset_layout_errors_first(tmp_path):
    repo_root, _ = make_repo(tmp_path)
    before = snapshot(repo_root)

    files = {"widget_maker.py": "", "bad.py": "", "static/app.txt": "ok"}
    result = generator.check_assets(COMPONENT_ID, files, repo_root=repo_root)
    assert normalize(result) == ("malformed_layout", ["bad.py:1: SyntaxError: x"])

    files_bad = {"widget_maker.py": "", "bad.py": "", "static/app.txt": "bad"}
    result = generator.check_assets(COMPONENT_ID, files_bad, repo_root=repo_root)
    assert normalize(result) == ("malformed_layout", ["static/app.txt: bad"])

    assert snapshot(repo_root) == before


def test_missing_declared_asset(tmp_path):
    repo_root, _ = make_repo(tmp_path)
    files = {"widget_maker.py": ""}
    result = generator.check_assets(COMPONENT_ID, files, repo_root=repo_root)
    assert normalize(result) == ("missing_asset", ["missing asset: static/app.txt"])


def test_bare_repo_without_component_md_passes(tmp_path):
    repo_root, _ = make_repo(tmp_path, with_component=False)
    files = {"widget_maker.py": ""}
    result = generator.check_assets(COMPONENT_ID, files, repo_root=repo_root)
    assert normalize(result) == (None, [])


def test_check_asset_environment_before_and_after_no_env(tmp_path):
    repo_root, log_path = make_repo(tmp_path)

    result = generator.check_asset_environment(COMPONENT_ID, repo_root=repo_root)
    assert normalize(result) == (None, [])
    calls = read_log(log_path)
    assert calls == ["python", "fake"]

    log_path.write_text("", encoding="utf-8")
    (repo_root / "NO_ENV").write_text("", encoding="utf-8")

    result = generator.check_asset_environment(COMPONENT_ID, repo_root=repo_root)
    assert normalize(result) == ("environment", ["fake needs fakeprog >= 2"])
    calls = read_log(log_path)
    assert calls
    assert calls[0] == "python"
    assert "fake" in calls


def test_check_asset_environment_unknown_kind(tmp_path):
    repo_root, log_path = make_repo(tmp_path, name="repo-unknown", kind="nosuchkind")
    result = generator.check_asset_environment(COMPONENT_ID, repo_root=repo_root)
    assert normalize(result) == ("environment", ["unknown asset kind: nosuchkind"])
    calls = read_log(log_path)
    assert calls and calls[0] == "python"