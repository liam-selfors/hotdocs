# hotdocs-criterion: sha256:322d37cd2c01cf4accb336a6ea71bb19b7623d1fa123cfd7f55c680c625e8b6b
"""AC-SURF-003: the command-line check (R-SURF-003) of check_surface."""

import os
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
    "def main(argv):\n"
    "    raise ValueError(" + repr("unknown argument: ") + " + repr(argv))\n"
)

COMPONENT_MD = (
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

LIBRARY_WITH_IMPLEMENTS = (
    "# Library\n"
    "\n"
    "A small command-line tool.\n"
    "\n"
    "Implements: `specs/architecture/cli-conventions.md`\n"
)

LIBRARY_WITHOUT_IMPLEMENTS = "# Library\n"


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_repo(repo_root, main_source, library_text):
    repo_root = Path(repo_root)
    _write(repo_root / "gen" / "kind-python" / "kind_python.py", PYTHON_ADAPTER)
    _write(repo_root / "specs" / "architecture" / "cli-conventions.md", "# CLI conventions\n")
    _write(repo_root / "specs" / "components" / "tool" / "component.md", COMPONENT_MD)
    _write(
        repo_root / "specs" / "components" / "tool" / "interface" / "library.md",
        library_text,
    )
    _write(repo_root / "gen" / "tool" / "tool.py", main_source)
    # The sealed source_path holds the same module, harmless either way.
    _write(repo_root / "legacy" / "tool" / "tool.py", main_source)
    return repo_root


def _findings(report):
    return list(field(report, "findings"))


def test_conforming_main_passes(tmp_path):
    repo_root = _build_repo(tmp_path / "repo", GOOD_MAIN, LIBRARY_WITH_IMPLEMENTS)
    report = surface_checker.check_surface("comp-tool", repo_root)
    assert _findings(report) == []
    assert field(report, "ok") is True


def test_raising_main_gives_one_cli_usage_finding(tmp_path):
    repo_root = _build_repo(tmp_path / "repo", RAISING_MAIN, LIBRARY_WITH_IMPLEMENTS)
    report = surface_checker.check_surface("comp-tool", repo_root)
    findings = _findings(report)
    assert len(findings) == 1, findings
    finding = findings[0]
    assert field(finding, "kind") == "cli_usage"
    message = field(finding, "message")
    assert "exit 1" in message
    assert "traceback" in message
    assert field(report, "ok") is False


def test_raising_main_without_implements_line_passes(tmp_path):
    repo_root = _build_repo(tmp_path / "repo", RAISING_MAIN, LIBRARY_WITHOUT_IMPLEMENTS)
    report = surface_checker.check_surface("comp-tool", repo_root)
    assert _findings(report) == []
    assert field(report, "ok") is True