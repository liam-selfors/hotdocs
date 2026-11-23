# hotdocs-criterion: sha256:cb61fcf1d5e7a74120acbde87907bed106120440fc363860eb24a30fb55462a2
import sys
from pathlib import Path

import surface_checker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


PYTHON_ADAPTER = (
    "import sys\n"
    "from pathlib import Path\n"
    "\n"
    "\n"
    "def provision(repo_root):\n"
    "    return {\"ok\": True, \"reason\": \"\", \"versions\": {}, \"lockfile_sha256\": None,\n"
    "            \"interpreter\": sys.executable}\n"
)

BAR_ONE = (
    "def fetch_one(x):\n"
    "    return x\n"
)

BAR_BOTH = (
    "def fetch_one(x):\n"
    "    return x\n"
    "\n"
    "\n"
    "def fetch_all():\n"
    "    return []\n"
)

WIDGET_LOAD_DEP = (
    "import importlib.util\n"
    "import os\n"
    "\n"
    "\n"
    "def _load_dep(repo_root, slug):\n"
    "    path = os.path.join(str(repo_root), 'gen', slug, slug + '.py')\n"
    "    spec = importlib.util.spec_from_file_location(slug, path)\n"
    "    module = importlib.util.module_from_spec(spec)\n"
    "    spec.loader.exec_module(module)\n"
    "    return module\n"
    "\n"
    "\n"
    "def run(repo_root):\n"
    "    bar_mod = _load_dep(repo_root, 'bar')\n"
    "    bar_mod.fetch_one(1)\n"
    "    bar_mod.fetch_all()\n"
    "    return bar_mod.__name__\n"
)


def widget_direct(last_line):
    return (
        "\"\"\"Widget module.\n"
        "\n"
        "uses bar.gone_a()\n"
        "\"\"\"\n"
        "import importlib.util\n"
        "\n"
        "# bar.gone_b is not called\n"
        "\n"
        "\n"
        "def load(directory):\n"
        "    spec = importlib.util.spec_from_file_location('bar', str(directory / 'bar.py'))\n"
        "    bar = importlib.util.module_from_spec(spec)\n"
        "    spec.loader.exec_module(bar)\n"
        "    " + last_line + "\n"
    )


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def build_repo(root, widget_source, bar_sealed=False):
    root.mkdir(parents=True, exist_ok=True)
    write(root / "gen" / "kind-python" / "kind_python.py", PYTHON_ADAPTER)

    write(
        root / "specs" / "components" / "widget" / "component.md",
        "---\n"
        "id: comp-widget\n"
        "title: Widget\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "depends_on: [comp-bar]\n"
        "---\n"
        "\n"
        "# Widget\n",
    )
    write(root / "specs" / "components" / "widget" / "interface" / "library.md", "# Library\n")
    write(root / "gen" / "widget" / "widget.py", widget_source)

    bar_front = (
        "---\n"
        "id: comp-bar\n"
        "title: Bar\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "depends_on: []\n"
    )
    if bar_sealed:
        bar_front += "sealed: true\n" + "source_path: legacy/bar/\n"
    bar_front += "---\n\n# Bar\n"
    write(root / "specs" / "components" / "bar" / "component.md", bar_front)
    write(root / "specs" / "components" / "bar" / "interface" / "library.md", "# Library\n")
    if bar_sealed:
        write(root / "legacy" / "bar" / "bar.py", BAR_BOTH)
    else:
        write(root / "gen" / "bar" / "bar.py", BAR_ONE)
    return root


EXPECTED = [{"kind": "dependency_name", "message": "bar has no fetch_all, which the candidate uses"}]


def findings_of(report):
    return [
        {"kind": field(f, "kind"), "message": field(f, "message")}
        for f in field(report, "findings")
    ]


def test_loaded_alias_missing_name_is_one_finding(tmp_path):
    root = build_repo(tmp_path / "r1", WIDGET_LOAD_DEP)
    report = surface_checker.check_surface("comp-widget", root)
    assert findings_of(report) == EXPECTED
    assert field(report, "ok") is False


def test_docstring_and_comment_uses_ignored(tmp_path):
    root = build_repo(tmp_path / "r2", widget_direct("return bar.fetch_one(1)"))
    report = surface_checker.check_surface("comp-widget", root)
    assert field(report, "ok") is True
    assert findings_of(report) == []


def test_direct_module_name_missing_use(tmp_path):
    root = build_repo(tmp_path / "r3", widget_direct("return bar.fetch_all()"))
    report = surface_checker.check_surface("comp-widget", root)
    assert findings_of(report) == EXPECTED
    assert field(report, "ok") is False


def test_sealed_dependency_found_at_source_path(tmp_path):
    for i, source in enumerate([widget_direct("return bar.fetch_all()"), WIDGET_LOAD_DEP]):
        root = build_repo(tmp_path / ("r4_" + str(i)), source, bar_sealed=True)
        assert not (root / "gen" / "bar").exists()
        report = surface_checker.check_surface("comp-widget", root)
        assert field(report, "ok") is True, findings_of(report)
        assert findings_of(report) == []