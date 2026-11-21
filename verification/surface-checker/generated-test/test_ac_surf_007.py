# hotdocs-criterion: sha256:a978848c59bb7fcdbc4aacdc26912d45c3b8d2db5cc72120548c8599a9bc52c8
import os
import sys
from pathlib import Path

import pytest

import surface_checker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _python_adapter_source(ok):
    if ok:
        body = (
            "    return {'ok': True, 'reason': '', 'versions': {}, "
            "'lockfile_sha256': None, "
            "'interpreter': str(Path(repo_root) / 'pywrap')}\n"
        )
    else:
        body = (
            "    return {'ok': False, 'reason': "
            + repr("python environment: no lock for you")
            + ", 'versions': {}, 'lockfile_sha256': None, "
            "'interpreter': None}\n"
        )
    return (
        "import sys\n"
        "from pathlib import Path\n"
        "\n"
        "\n"
        "def provision(repo_root):\n"
        + body
    )


def _build_repo(repo_root, provision_ok):
    # Component spec
    _write(
        repo_root / "specs" / "components" / "tool" / "component.md",
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
        "# Tool\n",
    )
    _write(
        repo_root / "specs" / "components" / "tool" / "interface" / "library.md",
        "# Library\n"
        "\n"
        "Implements: `specs/architecture/cli-conventions.md`\n",
    )

    # Candidate code
    _write(
        repo_root / "gen" / "tool" / "tool.py",
        "import os\n"
        "assert os.environ.get('HOTDOCS_WRAPPED') == '1'\n"
        "import sys\n"
        "\n"
        "\n"
        "def main(argv):\n"
        "    if os.environ.get('HOTDOCS_WRAPPED') == '1':\n"
        "        print("
        + repr("usage error: unknown argument")
        + ", file=sys.stderr)\n"
        "        return 2\n"
        "    return 0\n",
    )

    # Planted wrapper interpreter
    pywrap = repo_root / "pywrap"
    _write(
        pywrap,
        "#!/bin/sh\n"
        "HOTDOCS_WRAPPED=1 exec '" + sys.executable + "' \"$@\"\n",
    )
    os.chmod(pywrap, 0o755)

    # Planted python adapter
    _write(
        repo_root / "gen" / "kind-python" / "kind_python.py",
        _python_adapter_source(provision_ok),
    )


@pytest.mark.skipif(os.name == "nt", reason="planted wrapper interpreter is a POSIX shell script")
def test_wrapper_interpreter_is_used_for_candidate_subprocesses(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_repo(repo_root, provision_ok=True)

    report = surface_checker.check_surface("comp-tool", repo_root)

    assert field(report, "findings") == []
    assert field(report, "ok") is True


@pytest.mark.skipif(os.name == "nt", reason="planted wrapper interpreter is a POSIX shell script")
def test_failed_python_provision_gives_one_environment_finding(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_repo(repo_root, provision_ok=False)

    report = surface_checker.check_surface("comp-tool", repo_root)

    assert field(report, "findings") == [
        {"kind": "environment", "message": "python environment: no lock for you"}
    ]
    assert field(report, "ok") is False