# hotdocs-criterion: sha256:08b7a9629413738c69bb6ca1db2b676c9a141391e93b192dee77a7904ee7a953
import os
import sys
from pathlib import Path

import surface_checker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _plant_wrapper(repo_root):
    pywrap = repo_root / "pywrap"
    text = (
        "#!/bin/sh\n"
        + "HOTDOCS_WRAPPED=1 exec '" + sys.executable + "' \"$@\"\n"
    )
    pywrap.write_text(text)
    os.chmod(pywrap, 0o755)


OK_ADAPTER = (
    "import sys\n"
    "from pathlib import Path\n"
    "\n"
    "\n"
    "def provision(repo_root):\n"
    "    return {\"ok\": True, \"reason\": \"\", \"versions\": {}, \"lockfile_sha256\": None,\n"
    "            \"interpreter\": str(Path(repo_root) / \"pywrap\")}\n"
)

FAIL_ADAPTER = (
    "import sys\n"
    "from pathlib import Path\n"
    "\n"
    "\n"
    "def provision(repo_root):\n"
    "    return {\"ok\": False, \"reason\": "
    + repr("python environment: no lock for you")
    + ", \"versions\": {}, \"lockfile_sha256\": None,\n"
    "            \"interpreter\": None}\n"
)

TOOL_PY = (
    "import os\n"
    "assert os.environ.get('HOTDOCS_WRAPPED') == '1'\n"
    "import sys\n"
    "\n"
    "\n"
    "def main(argv):\n"
    "    if os.environ.get('HOTDOCS_WRAPPED') == '1':\n"
    "        print(" + repr("usage error: unknown argument") + ", file=sys.stderr)\n"
    "        return 2\n"
    "    return 0\n"
    "\n"
    "\n"
    "if __name__ == '__main__':\n"
    "    sys.exit(main(sys.argv[1:]))\n"
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

LIBRARY_MD = (
    "# Library\n"
    "\n"
    "A command-line tool with `main(argv)`.\n"
    "\n"
    "Implements: `specs/architecture/cli-conventions.md`\n"
)


def _build_repo(repo_root, adapter_source):
    _plant_wrapper(repo_root)
    _write(repo_root / "gen" / "kind-python" / "kind_python.py", adapter_source)
    _write(
        repo_root / "specs" / "architecture" / "asset-kind-python.md",
        "# Asset kind: python\n",
    )
    _write(
        repo_root / "specs" / "architecture" / "cli-conventions.md",
        "# CLI conventions\n\nAn unknown argument is a usage error, exit 2.\n",
    )
    _write(repo_root / "specs" / "components" / "tool" / "component.md", COMPONENT_MD)
    _write(
        repo_root / "specs" / "components" / "tool" / "interface" / "library.md",
        LIBRARY_MD,
    )
    _write(repo_root / "gen" / "tool" / "tool.py", TOOL_PY)


def test_wrapper_interpreter_runs_import_and_cli_checks(tmp_path, monkeypatch):
    monkeypatch.delenv("HOTDOCS_WRAPPED", raising=False)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_repo(repo_root, OK_ADAPTER)

    report = surface_checker.check_surface("comp-tool", repo_root)

    assert list(field(report, "findings")) == []
    assert field(report, "ok") is True


def test_python_provision_failure_is_single_environment_finding(tmp_path, monkeypatch):
    monkeypatch.delenv("HOTDOCS_WRAPPED", raising=False)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_repo(repo_root, FAIL_ADAPTER)

    report = surface_checker.check_surface("comp-tool", repo_root)

    findings = [
        {"kind": field(f, "kind"), "message": field(f, "message")}
        for f in field(report, "findings")
    ]
    assert findings == [
        {"kind": "environment", "message": "python environment: no lock for you"}
    ]
    assert field(report, "ok") is False