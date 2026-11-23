# hotdocs-criterion: sha256:22cfbc564f77422aa54b437a6f606466d103f6966c23882c4b88fa62b8f10924
import json
import os

import hotdocs_cli


def _write_logging_fake(project, log_path):
    base = project / "gen" / "spec-linter"
    base.mkdir(parents=True, exist_ok=True)
    source = (
        "import json\n"
        "\n"
        "def main(argv=None):\n"
        "    with open(" + repr(str(log_path)) + ", 'a', encoding='utf-8') as handle:\n"
        "        handle.write(json.dumps(argv) + '\\n')\n"
        "    return 7\n"
    )
    (base / "spec_linter.py").write_text(source, encoding="utf-8")


def _write_env_fake(project, log_path):
    base = project / "gen" / "spec-linter"
    base.mkdir(parents=True, exist_ok=True)
    source = (
        "import json\n"
        "import os\n"
        "\n"
        "def main(argv=None):\n"
        "    with open(" + repr(str(log_path)) + ", 'a', encoding='utf-8') as handle:\n"
        "        handle.write(json.dumps(os.environ.get(" + repr("VAR_HOTDOCS_CONFIG") + ")) + '\\n')\n"
        "    return 7\n"
    )
    (base / "spec_linter.py").write_text(source, encoding="utf-8")


def _read_log(log_path):
    if not log_path.exists():
        return []
    return [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _make_dirs(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    tool_root = tmp_path / "toolroot"
    tool_root.mkdir()
    return project, tool_root


def test_repo_root_appended_when_absent(tmp_path, monkeypatch):
    project, tool_root = _make_dirs(tmp_path)
    log_path = project / "calls.log"
    _write_logging_fake(project, log_path)
    monkeypatch.chdir(project)

    code = hotdocs_cli.run(["lint", "a.md"], tool_root=str(tool_root), cwd=str(project))

    assert code == 7
    calls = _read_log(log_path)
    assert calls == [["a.md", "--repo-root=" + os.path.abspath(str(project))]]


def test_repo_root_given_is_forwarded_unchanged(tmp_path, monkeypatch):
    project, tool_root = _make_dirs(tmp_path)
    log_path = project / "calls.log"
    _write_logging_fake(project, log_path)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)

    code1 = hotdocs_cli.run(
        ["lint", "--repo-root", str(project), "a.md"],
        tool_root=str(tool_root),
        cwd=str(elsewhere),
    )
    code2 = hotdocs_cli.run(
        ["lint", "--repo-root=" + str(project)],
        tool_root=str(tool_root),
        cwd=str(elsewhere),
    )

    assert code1 == 7
    assert code2 == 7
    calls = _read_log(log_path)
    assert calls == [
        ["--repo-root", str(project), "a.md"],
        ["--repo-root=" + str(project)],
    ]
    for call in calls:
        assert sum(1 for token in call if token.startswith("--repo-root")) == 1


def test_hotdocs_config_variable_set_and_restored(tmp_path, monkeypatch):
    project, tool_root = _make_dirs(tmp_path)
    (project / "hotdocs.toml").write_text('[project]\nname = "x"\n', encoding="utf-8")
    log_path = project / "calls.log"
    _write_env_fake(project, log_path)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)

    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    code1 = hotdocs_cli.run(
        ["lint", "--repo-root", str(project)],
        tool_root=str(tool_root),
        cwd=str(elsewhere),
    )
    assert code1 == 7
    assert "VAR_HOTDOCS_CONFIG" not in os.environ

    monkeypatch.setenv("VAR_HOTDOCS_CONFIG", "/x")
    code2 = hotdocs_cli.run(
        ["lint", "--repo-root", str(project)],
        tool_root=str(tool_root),
        cwd=str(elsewhere),
    )
    assert code2 == 7
    assert os.environ.get("VAR_HOTDOCS_CONFIG") == "/x"

    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    assert "VAR_HOTDOCS_CONFIG" not in os.environ

    seen = _read_log(log_path)
    assert len(seen) == 2
    assert seen[0] is not None
    assert os.path.realpath(seen[0]) == os.path.realpath(os.path.join(str(project), "hotdocs.toml"))
    assert seen[1] == "/x"