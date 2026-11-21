# hotdocs-criterion: sha256:efdaed6aab61e501f83bdf8ac83f4e4c5cf02ea775b41f5a43ec633401f140e9
import surface_checker

from pathlib import Path


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

WIDGET_SOURCE = (
    "import importlib.util\n"
    "from pathlib import Path\n"
    "\n"
    "\n"
    "def _load_dep(repo_root, slug):\n"
    "    path = Path(repo_root) / \"gen\" / slug / (slug + \".py\")\n"
    "    spec = importlib.util.spec_from_file_location(slug, path)\n"
    "    module = importlib.util.module_from_spec(spec)\n"
    "    spec.loader.exec_module(module)\n"
    "    return module\n"
    "\n"
    "\n"
    "def run(repo_root):\n"
    "    bar_mod = _load_dep(repo_root, 'bar')\n"
    "    first = bar_mod.fetch_one(1)\n"
    "    every = bar_mod.fetch_all()\n"
    "    name = bar_mod.__name__\n"
    "    return first, every, name\n"
)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def component_md(lines):
    return "---\n" + "".join(line + "\n" for line in lines) + "---\n\n# Component\n"


def build_repo(repo_root, bar_sealed):
    write(repo_root / "gen" / "kind-python" / "kind_python.py", PYTHON_ADAPTER)

    write(
        repo_root / "specs" / "components" / "widget" / "component.md",
        component_md([
            "id: comp-widget",
            "title: Widget",
            "status: draft",
            "owners: [test-team]",
            "depends_on: [comp-bar]",
        ]),
    )
    write(
        repo_root / "specs" / "components" / "widget" / "interface" / "library.md",
        "# Library\n",
    )
    write(repo_root / "gen" / "widget" / "widget.py", WIDGET_SOURCE)

    bar_lines = [
        "id: comp-bar",
        "title: Bar",
        "status: draft",
        "owners: [test-team]",
        "depends_on: []",
    ]
    if bar_sealed:
        bar_lines += ["sealed: true", "source_path: legacy/bar/"]
    write(
        repo_root / "specs" / "components" / "bar" / "component.md",
        component_md(bar_lines),
    )
    write(
        repo_root / "specs" / "components" / "bar" / "interface" / "library.md",
        "# Library\n",
    )

    if bar_sealed:
        write(
            repo_root / "legacy" / "bar" / "bar.py",
            "def fetch_one(x):\n"
            "    return x\n"
            "\n"
            "\n"
            "def fetch_all():\n"
            "    return []\n",
        )
    else:
        write(
            repo_root / "gen" / "bar" / "bar.py",
            "def fetch_one(x):\n"
            "    return x\n",
        )


def test_missing_dependency_name_via_load_helper_alias(tmp_path):
    repo_root = tmp_path / "repo"
    build_repo(repo_root, bar_sealed=False)

    report = surface_checker.check_surface("comp-widget", repo_root)

    findings = list(field(report, "findings"))
    assert len(findings) == 1, findings
    finding = findings[0]
    assert field(finding, "kind") == "dependency_name"
    assert field(finding, "message") == "bar has no fetch_all, which the candidate uses"
    assert field(report, "ok") is False


def test_sealed_dependency_with_all_names_passes(tmp_path):
    repo_root = tmp_path / "repo"
    build_repo(repo_root, bar_sealed=True)
    assert not (repo_root / "gen" / "bar").exists()

    report = surface_checker.check_surface("comp-widget", repo_root)

    assert list(field(report, "findings")) == []
    assert field(report, "ok") is True