# hotdocs-criterion: sha256:75b3d59907b5a3fab07ca984193910142193775185f7031274f44151e7511b9d
import json
import os
from pathlib import Path

import pytest

import hotdocs_cli


ENV_NAME = "VAR_HOTDOCS_CONFIG"


def _write_argv_fake(project):
    project = Path(project)
    log = project / "calls.log"
    d = project / "gen" / "spec-linter"
    d.mkdir(parents=True, exist_ok=True)
    src = (
        "import json\n"
        "\n"
        "def main(argv):\n"
        "    with open(" + repr(str(log)) + ", 'a', encoding='utf-8') as fh:\n"
        "        fh.write(json.dumps(list(argv)) + '\\n')\n"
        "    return 7\n"
    )
    (d / "spec_linter.py").write_text(src, encoding="utf-8")
    return log


def _write_env_fake(project):
    project = Path(project)
    log = project / "calls.log"
    d = project / "gen" / "spec-linter"
    d.mkdir(parents=True, exist_ok=True)
    src = (
        "import json\n"
        "import os\n"
        "\n"
        "def main(argv):\n"
        "    with open(" + repr(str(log)) + ", 'a', encoding='utf-8') as fh:\n"
        "        fh.write(json.dumps({'argv': list(argv), 'env': os.environ.get("
        + repr(ENV_NAME)
        + ")}) + '\\n')\n"
        "    return 7\n"
    )
    (d / "spec_linter.py").write_text(src, encoding="utf-8")
    return log


def _read_log(log):
    log = Path(log)
    if not log.is_file():
        return []
    return [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines() if line.strip()]


def _root_spellings(project):
    project = Path(project)
    return {
        str(project),
        str(project.resolve()),
        os.path.abspath(str(project)),
        os.path.realpath(str(project)),
    }


@pytest.fixture
def dirs(tmp_path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    tool_root = tmp_path / "toolroot"
    tool_root.mkdir()
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.delenv(ENV_NAME, raising=False)
    return project, tool_root, elsewhere


def test_repo_root_appended_when_absent(dirs, monkeypatch):
    project, tool_root, _ = dirs
    log = _write_argv_fake(project)
    monkeypatch.chdir(project)

    rc = hotdocs_cli.main(["lint", "a.md"], tool_root=str(tool_root), cwd=str(project))

    assert rc == 7
    calls = _read_log(log)
    assert len(calls) == 1
    argv = calls[0]
    assert len(argv) == 2
    assert argv[0] == "a.md"
    assert argv[1].startswith("--repo-root=")
    value = argv[1][len("--repo-root="):]
    assert os.path.isabs(value)
    assert value in _root_spellings(project)


def test_repo_root_separate_form_forwarded_unchanged(dirs, monkeypatch):
    project, tool_root, elsewhere = dirs
    log = _write_argv_fake(project)
    monkeypatch.chdir(elsewhere)

    tokens = ["--repo-root", str(project), "a.md"]
    rc = hotdocs_cli.main(["lint"] + tokens, tool_root=str(tool_root), cwd=str(elsewhere))

    assert rc == 7
    calls = _read_log(log)
    assert calls == [tokens]
    assert sum(1 for t in calls[0] if t.startswith("--repo-root")) == 1


def test_repo_root_equals_form_forwarded_unchanged(dirs, monkeypatch):
    project, tool_root, elsewhere = dirs
    log = _write_argv_fake(project)
    monkeypatch.chdir(elsewhere)

    tokens = ["--repo-root=" + str(project)]
    rc = hotdocs_cli.main(["lint"] + tokens, tool_root=str(tool_root), cwd=str(elsewhere))

    assert rc == 7
    calls = _read_log(log)
    assert calls == [tokens]


def test_config_env_set_from_project_and_restored(dirs, monkeypatch):
    project, tool_root, elsewhere = dirs
    (project / "hotdocs.toml").write_text("# project configuration\n", encoding="utf-8")
    log = _write_env_fake(project)
    monkeypatch.chdir(elsewhere)

    # Variable unset: the component sees the project's hotdocs.toml.
    monkeypatch.delenv(ENV_NAME, raising=False)
    rc = hotdocs_cli.main(
        ["lint", "--repo-root", str(project)], tool_root=str(tool_root), cwd=str(elsewhere)
    )
    assert rc == 7
    calls = _read_log(log)
    assert len(calls) == 1
    seen = calls[0]["env"]
    assert seen is not None
    assert Path(seen).name == "hotdocs.toml"
    assert Path(seen).resolve() == (project / "hotdocs.toml").resolve()
    assert ENV_NAME not in os.environ

    # Variable already set: left as given.
    monkeypatch.setenv(ENV_NAME, "/x")
    rc = hotdocs_cli.main(
        ["lint", "--repo-root", str(project)], tool_root=str(tool_root), cwd=str(elsewhere)
    )
    assert rc == 7
    calls = _read_log(log)
    assert len(calls) == 2
    assert calls[1]["env"] == "/x"
    assert os.environ.get(ENV_NAME) == "/x"