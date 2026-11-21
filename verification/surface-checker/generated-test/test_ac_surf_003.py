# hotdocs-criterion: sha256:2c6f2550d886010302a0c4528dcc5380372637b3a96c0f2a01d7bd2b1b75db7d
import sys
from pathlib import Path

import surface_checker


IMPLEMENTS_LINE = "Implements: `specs/architecture/cli-conventions.md`"


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
    "def main(argv):\n"
    "    raise ValueError(" + repr("unknown argument") + " + ': ' + repr(argv))\n"
)


def build_repo(repo_root, main_source, with_implements):
    repo_root = Path(repo_root)

    adapter_dir = repo_root / "gen" / "kind-python"
    adapter_dir.mkdir(parents=True, exist_ok=True)
    (adapter_dir / "kind_python.py").write_text(PYTHON_ADAPTER)

    comp_dir = repo_root / "specs" / "components" / "tool"
    (comp_dir / "interface").mkdir(parents=True, exist_ok=True)
    (comp_dir / "component.md").write_text(
        "---\n"
        "id: comp-tool\n"
        "title: Tool\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "depends_on: []\n"
        "sealed: true\n"
        "source_path: legacy/tool/\n"
        "---\n"
        "\n"
        "# Tool\n"
    )
    library = "# Library\n"
    if with_implements:
        library = library + "\n" + IMPLEMENTS_LINE + "\n"
    (comp_dir / "interface" / "library.md").write_text(library)

    code_dir = repo_root / "gen" / "tool"
    code_dir.mkdir(parents=True, exist_ok=True)
    (code_dir / "tool.py").write_text(main_source)

    legacy_dir = repo_root / "legacy" / "tool"
    legacy_dir.mkdir(parents=True, exist_ok=True)
    (legacy_dir / "tool.py").write_text(main_source)

    return code_dir


def test_conforming_main_gives_ok(tmp_path):
    repo_root = tmp_path / "repo"
    code_dir = build_repo(repo_root, GOOD_MAIN, with_implements=True)

    report = surface_checker.check_surface("comp-tool", repo_root, code_dir)

    findings = field(report, "findings")
    assert field(report, "ok") is True, findings
    assert list(findings) == []


def test_raising_main_gives_one_cli_usage_finding(tmp_path):
    repo_root = tmp_path / "repo"
    code_dir = build_repo(repo_root, RAISING_MAIN, with_implements=True)

    report = surface_checker.check_surface("comp-tool", repo_root, code_dir)

    findings = list(field(report, "findings"))
    assert field(report, "ok") is False
    assert len(findings) == 1, findings
    finding = findings[0]
    assert field(finding, "kind") == "cli_usage"
    message = field(finding, "message")
    assert "exit 1" in message
    assert "traceback" in message


def test_raising_main_without_implements_line_gives_ok(tmp_path):
    repo_root = tmp_path / "repo"
    code_dir = build_repo(repo_root, RAISING_MAIN, with_implements=False)

    report = surface_checker.check_surface("comp-tool", repo_root, code_dir)

    findings = field(report, "findings")
    assert field(report, "ok") is True, findings
    assert list(findings) == []