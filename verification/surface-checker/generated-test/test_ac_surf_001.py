# hotdocs-criterion: sha256:45a2aa42d920e147aba2ebfb8251a629c6537f5e5b6a11e51440396ff5ea7345
"""AC-SURF-001: the import check (R-SURF-001)."""

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


def build_repo(repo_root, module_source, with_depends_on):
    repo_root = Path(repo_root)

    adapter_dir = repo_root / "gen" / "kind-python"
    adapter_dir.mkdir(parents=True, exist_ok=True)
    (adapter_dir / "kind_python.py").write_text(PYTHON_ADAPTER)

    comp_dir = repo_root / "specs" / "components" / "widget"
    (comp_dir / "interface").mkdir(parents=True, exist_ok=True)
    lines = [
        "---",
        "id: comp-widget",
        "title: Widget",
        "status: draft",
        "owners: [test-team]",
    ]
    if with_depends_on:
        lines.append("depends_on: []")
    lines.append("---")
    lines.append("")
    lines.append("# Widget")
    lines.append("")
    (comp_dir / "component.md").write_text("\n".join(lines) + "\n")
    (comp_dir / "interface" / "library.md").write_text("# Library\n")

    code_dir = repo_root / "gen" / "widget"
    code_dir.mkdir(parents=True, exist_ok=True)
    (code_dir / "widget.py").write_text(module_source)
    return repo_root


def test_import_failure_gives_one_import_error_finding(tmp_path):
    repo_root = build_repo(tmp_path / "repo", "import nosuchmodule_xyz\n", True)

    report = surface_checker.check_surface("comp-widget", repo_root)

    assert field(report, "ok") is False
    findings = list(field(report, "findings"))
    assert len(findings) == 1, findings
    finding = findings[0]
    assert field(finding, "kind") == "import_error"
    assert "nosuchmodule_xyz" in field(finding, "message")


def test_clean_module_with_no_depends_on_passes(tmp_path):
    repo_root = build_repo(tmp_path / "repo", "X = 1\n", False)

    report = surface_checker.check_surface("comp-widget", repo_root)

    assert list(field(report, "findings")) == []
    assert field(report, "ok") is True