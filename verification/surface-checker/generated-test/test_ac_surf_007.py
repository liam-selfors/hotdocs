# hotdocs-criterion: sha256:f336bef519ff82f2943f12ef82907655d32a98ea4e0131df6c16d4dab4eb5215
"""AC-SURF-007 (covers R-SURF-006): the python adapter's provision runs first,
its interpreter runs every import subprocess, and an ok-False provision gives
exactly one environment finding."""

import os
import shutil
import sys
from pathlib import Path

import surface_checker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


TOOL_SOURCE = (
    "import os\n"
    "assert os.environ.get('HOTDOCS_WRAPPED') == '1'\n"
    "import sys\n"
    "\n"
    "\n"
    "def main(argv):\n"
    "    if os.environ.get('HOTDOCS_WRAPPED') == '1':\n"
    "        print('usage error: unknown argument', file=sys.stderr)\n"
    "        return 2\n"
    "    return 0\n"
    "\n"
    "\n"
    "if __name__ == '__main__':\n"
    "    sys.exit(main(sys.argv[1:]))\n"
)

ADAPTER_OK_SOURCE = (
    "import sys\n"
    "from pathlib import Path\n"
    "\n"
    "\n"
    "def provision(repo_root):\n"
    "    return {'ok': True, 'reason': '', 'versions': {}, 'lockfile_sha256': None,\n"
    "            'interpreter': str(Path(repo_root) / 'pywrap')}\n"
)

ADAPTER_FAIL_SOURCE = (
    "import sys\n"
    "from pathlib import Path\n"
    "\n"
    "\n"
    "def provision(repo_root):\n"
    "    return {'ok': False, 'reason': "
    + repr("python environment: no lock for you")
    + ", 'versions': {}, 'lockfile_sha256': None,\n"
    "            'interpreter': None}\n"
)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _write_adapter(repo_root, source):
    adapter_dir = repo_root / "gen" / "kind-python"
    _write(adapter_dir / "kind_python.py", source)
    shutil.rmtree(adapter_dir / "__pycache__", ignore_errors=True)


def _build_repo(repo_root):
    # The planted wrapper interpreter.
    pywrap = repo_root / "pywrap"
    _write(
        pywrap,
        "#!/bin/sh\n"
        + "HOTDOCS_WRAPPED=1 exec '" + sys.executable + "' \"$@\"\n",
    )
    os.chmod(pywrap, 0o755)

    # The python kind's definition and the planted adapter.
    _write(
        repo_root / "specs" / "architecture" / "asset-kind-python.md",
        "# Asset kind: python\n\nAny text.\n",
    )
    _write(
        repo_root / "specs" / "architecture" / "cli-conventions.md",
        "# CLI Conventions\n\nAny text.\n",
    )
    _write_adapter(repo_root, ADAPTER_OK_SOURCE)

    # The component comp-tool.
    comp_dir = repo_root / "specs" / "components" / "tool"
    _write(
        comp_dir / "component.md",
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
        "# Tool\n",
    )
    _write(
        comp_dir / "interface" / "library.md",
        "# Library\n"
        "\n"
        "main(argv: list[str]) -> int\n"
        "\n"
        "Implements: `specs/architecture/cli-conventions.md`\n",
    )

    # The candidate module (also at the sealed source_path, harmlessly).
    _write(repo_root / "gen" / "tool" / "tool.py", TOOL_SOURCE)
    _write(repo_root / "legacy" / "tool" / "tool.py", TOOL_SOURCE)


def test_ac_surf_007(tmp_path, monkeypatch):
    monkeypatch.delenv("HOTDOCS_WRAPPED", raising=False)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_repo(repo_root)

    # Scenario 1: the wrapper interpreter runs the candidate's subprocesses.
    report = surface_checker.check_surface("comp-tool", repo_root)
    findings = field(report, "findings")
    assert findings == []
    assert field(report, "ok") is True

    # Scenario 2: provision reports ok False; exactly one environment finding.
    _write_adapter(repo_root, ADAPTER_FAIL_SOURCE)
    report = surface_checker.check_surface("comp-tool", repo_root)
    findings = field(report, "findings")
    assert findings == [
        {"kind": "environment", "message": "python environment: no lock for you"}
    ]
    assert field(report, "ok") is False