# hotdocs-criterion: sha256:71950cd439ad9b1a4b33aa465a09cf52b25298139c808407a949e9c8633f3750
import json
import os
from pathlib import Path

import pytest

import hotdocs_cli


VAR = "VAR_HOTDOCS_CONFIG"


def write_fake_lint(project, record_env=False):
    project = Path(project)
    log_path = str(project / "calls.log")
    env_log_path = str(project / "env.log")
    target = project / "gen" / "spec-linter" / "spec_linter.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    src = (
        "import json\n"
        "import os\n"
        "\n"
        "LOG_PATH = " + repr(log_path) + "\n"
        "ENV_LOG_PATH = " + repr(env_log_path) + "\n"
        "RECORD_ENV = " + repr(bool(record_env)) + "\n"
        "\n"
        "def main(argv=None):\n"
        "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(json.dumps(argv) + '\\n')\n"
        "    if RECORD_ENV:\n"
        "        with open(ENV_LOG_PATH, 'a', encoding='utf-8') as fh:\n"
        "            fh.write(json.dumps(os.environ.get(" + repr(VAR) + ")) + '\\n')\n"
        "    return 7\n"
    )
    target.write_text(src, encoding="utf-8")
    return Path(log_path), Path(env_log_path)


def read_lines(path):
    path = Path(path)
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def make_dirs(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    tool_root = tmp_path / "toolroot"
    tool_root.mkdir()
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    return project, tool_root, elsewhere


def quiet(*args, **kwargs):
    pass


def test_repo_root_appended_from_cwd_when_absent(tmp_path, monkeypatch):
    monkeypatch.delenv(VAR, raising=False)
    project, tool_root, _ = make_dirs(tmp_path)
    log_path, _ = write_fake_lint(project)

    rc = hotdocs_cli.run(
        ["lint", "a.md"],
        tool_root=str(tool_root),
        output_fn=quiet,
        cwd=str(project),
    )

    assert rc == 7
    calls = read_lines(log_path)
    assert calls == [["a.md", "--repo-root=" + os.path.abspath(str(project))]]


def test_repo_root_present_forwarded_unchanged(tmp_path, monkeypatch):
    monkeypatch.delenv(VAR, raising=False)
    project, tool_root, elsewhere = make_dirs(tmp_path)
    log_path, _ = write_fake_lint(project)
    proj = str(project)

    rc1 = hotdocs_cli.run(
        ["lint", "--repo-root", proj, "a.md"],
        tool_root=str(tool_root),
        output_fn=quiet,
        cwd=str(elsewhere),
    )
    rc2 = hotdocs_cli.run(
        ["lint", "--repo-root=" + proj],
        tool_root=str(tool_root),
        output_fn=quiet,
        cwd=str(elsewhere),
    )

    assert rc1 == 7
    assert rc2 == 7
    calls = read_lines(log_path)
    assert calls == [
        ["--repo-root", proj, "a.md"],
        ["--repo-root=" + proj],
    ]
    for call in calls:
        assert sum(1 for t in call if t == "--repo-root" or t.startswith("--repo-root=")) == 1


def test_hotdocs_config_var_set_while_running_and_restored(tmp_path, monkeypatch):
    project, tool_root, elsewhere = make_dirs(tmp_path)
    (project / "hotdocs.toml").write_text("", encoding="utf-8")
    log_path, env_log_path = write_fake_lint(project, record_env=True)
    proj = str(project)

    monkeypatch.chdir(str(elsewhere))
    monkeypatch.delenv(VAR, raising=False)

    rc1 = hotdocs_cli.run(
        ["lint", "--repo-root", proj],
        tool_root=str(tool_root),
        output_fn=quiet,
        cwd=str(elsewhere),
    )
    assert rc1 == 7
    assert VAR not in os.environ

    monkeypatch.setenv(VAR, "/x")
    rc2 = hotdocs_cli.run(
        ["lint", "--repo-root", proj],
        tool_root=str(tool_root),
        output_fn=quiet,
        cwd=str(elsewhere),
    )
    assert rc2 == 7
    assert os.environ.get(VAR) == "/x"

    seen = read_lines(env_log_path)
    assert len(seen) == 2
    assert seen[0] is not None
    assert os.path.realpath(seen[0]) == os.path.realpath(os.path.join(proj, "hotdocs.toml"))
    assert seen[1] == "/x"

    calls = read_lines(log_path)
    assert calls == [["--repo-root", proj], ["--repo-root", proj]]