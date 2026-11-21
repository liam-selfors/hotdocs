# hotdocs-criterion: sha256:471c37a92a4f7d0ecf283c263a58e0d75727de9f9b7cd577c9453056fd94a366
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


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _component_md(lines):
    return "---\n" + "".join(line + "\n" for line in lines) + "---\n\n# Component\n"


def _base_repo(repo_root):
    _write(repo_root / "gen" / "kind-python" / "kind_python.py", PYTHON_ADAPTER)
    _write(
        repo_root / "specs" / "components" / "widget" / "component.md",
        _component_md([
            "id: comp-widget",
            "title: Widget",
            "status: draft",
            "owners: [team-a]",
            "depends_on: [comp-bar]",
        ]),
    )
    _write(
        repo_root / "specs" / "components" / "widget" / "interface" / "library.md",
        "# Library\n",
    )
    _write(repo_root / "gen" / "widget" / "widget.py", WIDGET_SOURCE)


def test_missing_name_through_load_helper_alias(tmp_path):
    repo_root = tmp_path / "repo"
    _base_repo(repo_root)
    _write(
        repo_root / "specs" / "components" / "bar" / "component.md",
        _component_md([
            "id: comp-bar",
            "title: Bar",
            "status: draft",
            "owners: [team-a]",
            "depends_on: []",
        ]),
    )
    _write(
        repo_root / "specs" / "components" / "bar" / "interface" / "library.md",
        "# Library\n",
    )
    _write(
        repo_root / "gen" / "bar" / "bar.py",
        "def fetch_one(key):\n    return key\n",
    )

    report = surface_checker.check_surface("comp-widget", repo_root)
    findings = list(field(report, "findings"))
    assert len(findings) == 1, findings
    assert field(findings[0], "kind") == "dependency_name"
    assert field(findings[0], "message") == "bar has no fetch_all, which the candidate uses"
    assert field(report, "ok") is False


def test_sealed_dependency_with_all_names_passes(tmp_path):
    repo_root = tmp_path / "repo"
    _base_repo(repo_root)
    _write(
        repo_root / "specs" / "components" / "bar" / "component.md",
        _component_md([
            "id: comp-bar",
            "title: Bar",
            "status: draft",
            "owners: [team-a]",
            "depends_on: []",
            "sealed: true",
            "source_path: legacy/bar/",
        ]),
    )
    _write(
        repo_root / "specs" / "components" / "bar" / "interface" / "library.md",
        "# Library\n",
    )
    _write(
        repo_root / "legacy" / "bar" / "bar.py",
        "def fetch_one(key):\n    return key\n\n\ndef fetch_all():\n    return []\n",
    )
    assert not (repo_root / "gen" / "bar").exists()

    report = surface_checker.check_surface("comp-widget", repo_root)
    assert field(report, "ok") is True, field(report, "findings")