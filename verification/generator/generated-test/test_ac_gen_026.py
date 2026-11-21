# hotdocs-criterion: sha256:9c73e70d1324d0b0b8aa23fd4af874103898372980c95f59a0adddb62e245a18
import sys
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

FAKE_ADAPTER_HEAD = (
    "from pathlib import Path\n"
    "\n"
    "KIND = \"fake\"\n"
    "\n"
    "\n"
    "def layout_errors(asset_file):\n"
    "    return [\"bad\"] if \"bad\" in Path(asset_file).read_text(encoding=\"utf-8\") else []\n"
    "\n"
    "\n"
)

FAKE_PROVISION_BODY = (
    "    if (Path(repo_root) / \"NO_ENV\").exists():\n"
    "        return {\"ok\": False, \"reason\": \"fake needs fakeprog >= 2\", \"versions\": {}, \"lockfile_sha256\": None}\n"
    "    return {\"ok\": True, \"reason\": \"\", \"versions\": {\"fakeprog\": \"2.0.0\"}, \"lockfile_sha256\": None}\n"
)

PYTHON_ADAPTER_HEAD = (
    "from pathlib import Path\n"
    "\n"
    "KIND = \"python\"\n"
    "\n"
    "\n"
    "def layout_errors(code_dir):\n"
    "    return [\"bad.py:1: SyntaxError: x\"] if (Path(code_dir) / \"bad.py\").exists() else []\n"
    "\n"
    "\n"
)

PYTHON_PROVISION_BODY = (
    "    return {\"ok\": True, \"reason\": \"\", \"versions\": {\"python\": \"3.12\"}, \"lockfile_sha256\": None, \"interpreter\": \"/fake/python\"}\n"
)


def _log_lines(log_path, label):
    if log_path is None:
        return ""
    return (
        "    with open(" + repr(str(log_path)) + ", \"a\", encoding=\"utf-8\") as _f:\n"
        "        _f.write(" + repr(label + "\n") + ")\n"
    )


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def plant_python_adapter(repo_root, log_path=None):
    source = (
        PYTHON_ADAPTER_HEAD
        + "def provision(repo_root):\n"
        + _log_lines(log_path, "python")
        + PYTHON_PROVISION_BODY
    )
    _write(repo_root / "gen" / "kind-python" / "kind_python.py", source)


def plant_fake_kind(repo_root, log_path=None):
    definition = "# Fake\n"
    for name in SECTIONS:
        definition += "\n## " + name + "\n\nx\n"
    _write(repo_root / "specs" / "architecture" / "asset-kind-fake.md", definition)
    source = (
        FAKE_ADAPTER_HEAD
        + "def provision(repo_root):\n"
        + _log_lines(log_path, "fake")
        + FAKE_PROVISION_BODY
    )
    _write(repo_root / "gen" / "kind-fake" / "kind_fake.py", source)


def plant_component(repo_root, kind="fake"):
    text = (
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
    _write(repo_root / "specs" / "components" / "widget-maker" / "component.md", text)


def make_repo(tmp_path, kind="fake", log_path=None, component=True):
    repo_root = tmp_path / "repo"
    repo_root.mkdir(parents=True, exist_ok=True)
    plant_python_adapter(repo_root, log_path)
    if component:
        plant_fake_kind(repo_root, log_path)
        plant_component(repo_root, kind)
    return repo_root


def snapshot(repo_root):
    result = set()
    for p in repo_root.rglob("*"):
        rel = p.relative_to(repo_root)
        if "__pycache__" in rel.parts or p.suffix == ".pyc":
            continue
        result.add(rel.as_posix())
    return result


def normalize(result):
    category, messages = result
    return (category, list(messages))


def test_undeclared_files_sorted_and_nothing_written(tmp_path):
    repo_root = make_repo(tmp_path)
    before = snapshot(repo_root)
    files = {"widget_maker.py": "", "static/app.txt": "ok", "b.md": "", "a.json": ""}
    result = generator.check_assets(COMPONENT_ID, files, repo_root=repo_root)
    assert normalize(result) == (
        "malformed_layout",
        ["undeclared file: a.json", "undeclared file: b.md"],
    )
    assert snapshot(repo_root) == before


def test_package_layout_passes(tmp_path):
    repo_root = make_repo(tmp_path)
    before = snapshot(repo_root)
    files = {"widget_maker/__init__.py": "", "static/app.txt": "ok"}
    result = generator.check_assets(COMPONENT_ID, files, repo_root=repo_root)
    assert normalize(result) == (None, [])
    assert snapshot(repo_root) == before


def test_python_layout_errors(tmp_path):
    repo_root = make_repo(tmp_path)
    files = {"widget_maker.py": "", "bad.py": "", "static/app.txt": "ok"}
    result = generator.check_assets(COMPONENT_ID, files, repo_root=repo_root)
    assert normalize(result) == ("malformed_layout", ["bad.py:1: SyntaxError: x"])


def test_declared_asset_layout_errors_first(tmp_path):
    repo_root = make_repo(tmp_path)
    files = {"widget_maker.py": "", "bad.py": "", "static/app.txt": "bad"}
    result = generator.check_assets(COMPONENT_ID, files, repo_root=repo_root)
    assert normalize(result) == ("malformed_layout", ["static/app.txt: bad"])


def test_missing_asset(tmp_path):
    repo_root = make_repo(tmp_path)
    files = {"widget_maker.py": ""}
    result = generator.check_assets(COMPONENT_ID, files, repo_root=repo_root)
    assert normalize(result) == ("missing_asset", ["missing asset: static/app.txt"])


def test_bare_repo_root_without_component_md(tmp_path):
    repo_root = make_repo(tmp_path, component=False)
    assert not (repo_root / "specs" / "components" / "widget-maker" / "component.md").exists()
    files = {"widget_maker.py": ""}
    result = generator.check_assets(COMPONENT_ID, files, repo_root=repo_root)
    assert normalize(result) == (None, [])


def test_check_asset_environment_before_and_after_no_env(tmp_path):
    log_path = tmp_path / "provision.log"
    repo_root = make_repo(tmp_path, log_path=log_path)

    first = generator.check_asset_environment(COMPONENT_ID, repo_root=repo_root)
    assert normalize(first) == (None, [])
    lines = log_path.read_text(encoding="utf-8").splitlines()
    assert lines, "no provision was called"
    assert lines[0] == "python"
    assert "fake" in lines
    assert lines.index("python") < lines.index("fake")

    (repo_root / "NO_ENV").write_text("", encoding="utf-8")
    log_path.write_text("", encoding="utf-8")

    second = generator.check_asset_environment(COMPONENT_ID, repo_root=repo_root)
    assert normalize(second) == ("environment", ["fake needs fakeprog >= 2"])
    lines = log_path.read_text(encoding="utf-8").splitlines()
    assert lines and lines[0] == "python"
    assert "fake" in lines
    assert lines.index("python") < lines.index("fake")


def test_check_asset_environment_unknown_kind(tmp_path):
    repo_root = make_repo(tmp_path, kind="nosuchkind")
    result = generator.check_asset_environment(COMPONENT_ID, repo_root=repo_root)
    assert normalize(result) == ("environment", ["unknown asset kind: nosuchkind"])