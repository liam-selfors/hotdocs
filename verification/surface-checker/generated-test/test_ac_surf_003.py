# hotdocs-criterion: sha256:85fc34a8a225d17b5301ef87a6a11b75c8292d984b0cf7c2a6dc8d68f1fa17e8
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

USAGE_MAIN = (
    "import sys\n"
    "\n"
    "\n"
    "def main(argv):\n"
    "    print(" + repr("usage error: unknown argument") + ", file=sys.stderr)\n"
    "    return 2\n"
)

RAISING_MAIN = (
    "def main(argv):\n"
    "    raise ValueError(" + repr("unknown argument") + ")\n"
)


def build_repo(root, main_source, implements):
    root = Path(root)
    adapter_dir = root / "gen" / "kind-python"
    adapter_dir.mkdir(parents=True, exist_ok=True)
    (adapter_dir / "kind_python.py").write_text(PYTHON_ADAPTER)

    arch = root / "specs" / "architecture"
    arch.mkdir(parents=True, exist_ok=True)
    (arch / "cli-conventions.md").write_text("# CLI Conventions\n\nAny text.\n")

    comp = root / "specs" / "components" / "tool"
    (comp / "interface").mkdir(parents=True, exist_ok=True)
    (comp / "component.md").write_text(
        "---\n"
        "id: comp-tool\n"
        "title: Tool\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "depends_on: []\n"
        "sealed: true\n"
        "source_path: legacy/tool/\n"
        "---\n"
        "\n"
        "# Tool\n"
    )
    library = "# Library\n\nA command-line tool.\n"
    if implements:
        library += "\nImplements: `specs/architecture/cli-conventions.md`\n"
    (comp / "interface" / "library.md").write_text(library)

    code = root / "gen" / "tool"
    code.mkdir(parents=True, exist_ok=True)
    (code / "tool.py").write_text(main_source)
    return root


def test_usage_error_main_passes(tmp_path):
    repo_root = build_repo(tmp_path / "repo", USAGE_MAIN, implements=True)
    report = surface_checker.check_surface("comp-tool", repo_root)
    assert field(report, "findings") == [] or list(field(report, "findings")) == []
    assert field(report, "ok") is True


def test_raising_main_gives_one_cli_usage_finding(tmp_path):
    repo_root = build_repo(tmp_path / "repo", RAISING_MAIN, implements=True)
    report = surface_checker.check_surface("comp-tool", repo_root)
    findings = list(field(report, "findings"))
    assert len(findings) == 1, findings
    finding = findings[0]
    assert field(finding, "kind") == "cli_usage"
    message = field(finding, "message")
    assert "exit 1" in message
    assert "traceback" in message
    assert field(report, "ok") is False


def test_raising_main_without_implements_line_passes(tmp_path):
    repo_root = build_repo(tmp_path / "repo", RAISING_MAIN, implements=False)
    report = surface_checker.check_surface("comp-tool", repo_root)
    assert list(field(report, "findings")) == []
    assert field(report, "ok") is True