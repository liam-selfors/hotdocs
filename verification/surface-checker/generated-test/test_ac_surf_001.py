# hotdocs-criterion: sha256:7489d8a7b9f842bfbd91ac62fd5427e2e0202814b85b54f8c1cdaaf968763ede
"""AC-SURF-001: a candidate whose import fails gives exactly one import_error
finding; a candidate that imports cleanly with no dependencies gives none."""

from pathlib import Path

import surface_checker


PYTHON_ADAPTER = (
    "import sys\n"
    "from pathlib import Path\n"
    "\n"
    "\n"
    "def provision(repo_root):\n"
    "    return {\"ok\": True, \"reason\": \"\", \"versions\": {}, \"lockfile_sha256\": None,\n"
    "            \"interpreter\": sys.executable}\n"
)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_repo(repo_root, module_source, with_depends_on):
    repo_root = Path(repo_root)
    _write(repo_root / "gen" / "kind-python" / "kind_python.py", PYTHON_ADAPTER)
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
    _write(
        repo_root / "specs" / "components" / "widget" / "component.md",
        "\n".join(lines),
    )
    _write(
        repo_root / "specs" / "components" / "widget" / "interface" / "library.md",
        "# Library\n",
    )
    _write(repo_root / "gen" / "widget" / "widget.py", module_source)
    return repo_root


def test_import_failure_gives_one_import_error_finding(tmp_path):
    repo_root = _build_repo(
        tmp_path / "repo", "import nosuchmodule_xyz\n", with_depends_on=True
    )

    report = surface_checker.check_surface("comp-widget", repo_root)

    assert field(report, "ok") is False
    findings = field(report, "findings")
    assert len(findings) == 1, findings
    finding = findings[0]
    assert field(finding, "kind") == "import_error"
    assert "nosuchmodule_xyz" in field(finding, "message")


def test_clean_import_without_dependencies_gives_no_findings(tmp_path):
    repo_root = _build_repo(tmp_path / "repo", "X = 1\n", with_depends_on=False)

    report = surface_checker.check_surface("comp-widget", repo_root)

    assert field(report, "ok") is True
    assert list(field(report, "findings")) == []