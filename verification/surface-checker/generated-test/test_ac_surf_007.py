# hotdocs-criterion: sha256:451af84204b696025862e5c8c5464f1a40e48fa224105bb51de37c8342a99d18
import os
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
    "        print(" + repr("usage error: unknown argument") + ", file=sys.stderr)\n"
    "        return 2\n"
    "    return 0\n"
)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _build_repo(repo_root, provision_ok):
    repo_root = Path(repo_root)

    # component.md
    _write(
        repo_root / "specs" / "components" / "tool" / "component.md",
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

    # interface/library.md ending with the Implements line
    _write(
        repo_root / "specs" / "components" / "tool" / "interface" / "library.md",
        "# Library\n"
        "\n"
        "Implements: `specs/architecture/cli-conventions.md`\n",
    )

    # candidate module
    _write(repo_root / "gen" / "tool" / "tool.py", TOOL_SOURCE)
    # same source at the sealed source_path, harmless
    _write(repo_root / "legacy" / "tool" / "tool.py", TOOL_SOURCE)

    # planted wrapper interpreter
    pywrap = repo_root / "pywrap"
    pywrap.write_text(
        "#!/bin/sh\n"
        "HOTDOCS_WRAPPED=1 exec '" + sys.executable + "' \"$@\"\n"
    )
    os.chmod(pywrap, 0o755)

    # planted python adapter
    if provision_ok:
        provision_body = (
            "def provision(repo_root):\n"
            "    return {\"ok\": True, \"reason\": \"\", \"versions\": {},\n"
            "            \"lockfile_sha256\": None,\n"
            "            \"interpreter\": str(Path(repo_root) / " + repr("pywrap") + ")}\n"
        )
    else:
        provision_body = (
            "def provision(repo_root):\n"
            "    return {\"ok\": False, \"reason\": "
            + repr("python environment: no lock for you")
            + ", \"versions\": {},\n"
            "            \"lockfile_sha256\": None, \"interpreter\": None}\n"
        )
    _write(
        repo_root / "gen" / "kind-python" / "kind_python.py",
        "import sys\n"
        "from pathlib import Path\n"
        "\n"
        "KIND = " + repr("python") + "\n"
        "\n"
        "\n" + provision_body,
    )
    return repo_root


def test_wrapper_interpreter_is_used_for_candidate_subprocesses(tmp_path, monkeypatch):
    monkeypatch.delenv("HOTDOCS_WRAPPED", raising=False)
    repo_root = _build_repo(tmp_path / "repo", provision_ok=True)

    report = surface_checker.check_surface("comp-tool", repo_root)

    findings = field(report, "findings")
    assert findings == []
    assert field(report, "ok") is True


def test_provision_failure_gives_single_environment_finding(tmp_path, monkeypatch):
    monkeypatch.delenv("HOTDOCS_WRAPPED", raising=False)
    repo_root = _build_repo(tmp_path / "repo", provision_ok=False)

    report = surface_checker.check_surface("comp-tool", repo_root)

    findings = field(report, "findings")
    normalized = [
        {"kind": field(f, "kind"), "message": field(f, "message")} for f in findings
    ]
    assert normalized == [
        {"kind": "environment", "message": "python environment: no lock for you"}
    ]
    assert field(report, "ok") is False