# hotdocs-criterion: sha256:edbc65fe967689e661b7fa9c8e63509233cc3478895b3d56b4397589f15032a9
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


def build_repo(repo_root, widget_source):
    repo_root = Path(repo_root)
    comp_dir = repo_root / "specs" / "components" / "widget"
    (comp_dir / "interface").mkdir(parents=True)
    (comp_dir / "component.md").write_text(
        "---\n"
        + "id: comp-widget\n"
        + "title: Widget\n"
        + "status: draft\n"
        + "owners: [test-team]\n"
        + "depends_on: []\n"
        + "---\n"
        + "\n"
        + "# Widget\n"
    )
    (comp_dir / "interface" / "library.md").write_text("# Library\n")

    gen_widget = repo_root / "gen" / "widget"
    gen_widget.mkdir(parents=True)
    (gen_widget / "widget.py").write_text(widget_source)

    adapter_dir = repo_root / "gen" / "kind-python"
    adapter_dir.mkdir(parents=True)
    (adapter_dir / "kind_python.py").write_text(PYTHON_ADAPTER)
    return repo_root


def test_import_failure_gives_one_import_error_finding(tmp_path):
    repo_root = build_repo(tmp_path / "repo", "import nosuchmodule_xyz\n")

    report = surface_checker.check_surface("comp-widget", repo_root)

    assert field(report, "ok") is False
    findings = field(report, "findings")
    assert len(findings) == 1
    finding = findings[0]
    assert field(finding, "kind") == "import_error"
    assert "nosuchmodule_xyz" in field(finding, "message")


def test_importable_module_without_dependencies_passes(tmp_path):
    repo_root = build_repo(tmp_path / "repo", "X = 1\n")

    report = surface_checker.check_surface("comp-widget", repo_root)

    assert field(report, "ok") is True
    assert list(field(report, "findings")) == []