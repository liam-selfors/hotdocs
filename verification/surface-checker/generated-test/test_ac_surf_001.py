# hotdocs-criterion: sha256:2b6c07e692943368c565f82ce3998c1852e8f2263e89159df3bcd5cc37868e68
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


def build_repo(repo_root, module_source):
    repo_root = Path(repo_root)
    comp_dir = repo_root / "specs" / "components" / "widget"
    (comp_dir / "interface").mkdir(parents=True, exist_ok=True)
    (comp_dir / "component.md").write_text(
        "---\n"
        "id: comp-widget\n"
        "title: Widget\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "depends_on: []\n"
        "sealed: true\n"
        "source_path: legacy/widget/\n"
        "---\n"
        "\n"
        "# Widget\n"
    )
    (comp_dir / "interface" / "library.md").write_text("# Library\n")

    adapter_dir = repo_root / "gen" / "kind-python"
    adapter_dir.mkdir(parents=True, exist_ok=True)
    (adapter_dir / "kind_python.py").write_text(PYTHON_ADAPTER)

    code_dir = repo_root / "gen" / "widget"
    code_dir.mkdir(parents=True, exist_ok=True)
    (code_dir / "widget.py").write_text(module_source)
    return repo_root


def test_import_error_gives_one_import_error_finding(tmp_path):
    repo_root = build_repo(tmp_path / "repo", "import nosuchmodule_xyz\n")

    report = surface_checker.check_surface("comp-widget", repo_root)

    assert field(report, "ok") is False
    findings = list(field(report, "findings"))
    assert len(findings) == 1, findings
    finding = findings[0]
    assert field(finding, "kind") == "import_error"
    assert "nosuchmodule_xyz" in field(finding, "message")


def test_importable_module_without_dependencies_passes(tmp_path):
    repo_root = build_repo(tmp_path / "repo", "X = 1\n")

    report = surface_checker.check_surface("comp-widget", repo_root)

    assert field(report, "ok") is True
    assert list(field(report, "findings")) == []