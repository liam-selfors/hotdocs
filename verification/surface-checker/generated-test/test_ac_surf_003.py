# hotdocs-criterion: sha256:f1dd5e2ba31835d4b5fb07ab9041955aaee125cc3b920de02dd0563a8293e5df
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

GOOD_MAIN = (
    "import sys\n"
    "\n"
    "\n"
    "def main(argv):\n"
    "    print(" + repr("usage error: unknown argument") + ", file=sys.stderr)\n"
    "    return 2\n"
)

RAISING_MAIN = (
    "import sys\n"
    "\n"
    "\n"
    "def main(argv):\n"
    "    raise ValueError(" + repr("unknown argument") + ")\n"
)

IMPLEMENTS_LIBRARY = (
    "# Library\n"
    "\n"
    "main(argv: list[str]) -> int\n"
    "\n"
    "Implements: `specs/architecture/cli-conventions.md`\n"
)

PLAIN_LIBRARY = "# Library\n\nmain(argv: list[str]) -> int\n"


def build_repo(root, main_source, library_text):
    root = Path(root)
    comp_dir = root / "specs" / "components" / "tool"
    (comp_dir / "interface").mkdir(parents=True)
    (comp_dir / "component.md").write_text(
        "---\n"
        "id: comp-tool\n"
        "title: Tool\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "depends_on: []\n"
        "---\n"
        "\n"
        "# Tool\n"
    )
    (comp_dir / "interface" / "library.md").write_text(library_text)
    arch = root / "specs" / "architecture"
    arch.mkdir(parents=True)
    (arch / "cli-conventions.md").write_text("# CLI conventions\n")
    adapter_dir = root / "gen" / "kind-python"
    adapter_dir.mkdir(parents=True)
    (adapter_dir / "kind_python.py").write_text(PYTHON_ADAPTER)
    code_dir = root / "gen" / "tool"
    code_dir.mkdir(parents=True)
    (code_dir / "tool.py").write_text(main_source)
    return root, code_dir


def test_cli_usage_conforming_main_passes(tmp_path):
    repo_root, code_dir = build_repo(tmp_path, GOOD_MAIN, IMPLEMENTS_LIBRARY)
    report = surface_checker.check_surface("comp-tool", repo_root)
    assert field(report, "findings") == []
    assert field(report, "ok") is True


def test_cli_usage_raising_main_gives_one_finding(tmp_path):
    repo_root, code_dir = build_repo(tmp_path, RAISING_MAIN, IMPLEMENTS_LIBRARY)
    report = surface_checker.check_surface("comp-tool", repo_root)
    findings = field(report, "findings")
    assert len(findings) == 1, findings
    finding = findings[0]
    assert field(finding, "kind") == "cli_usage"
    message = field(finding, "message")
    assert "exit 1" in message
    assert "traceback" in message
    assert field(report, "ok") is False


def test_cli_usage_not_checked_without_implements_line(tmp_path):
    repo_root, code_dir = build_repo(tmp_path, RAISING_MAIN, PLAIN_LIBRARY)
    report = surface_checker.check_surface("comp-tool", repo_root)
    assert field(report, "findings") == []
    assert field(report, "ok") is True