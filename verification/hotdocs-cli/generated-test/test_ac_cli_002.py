# hotdocs-criterion: sha256:a3f10ba0f3537150d7fc6a186685331f08a92641b6856fa5af436baee8c45a54
import json
import os
from pathlib import Path

import hotdocs_cli


def _make_project(base, name):
    project = base / name
    project.mkdir(parents=True)
    return project


def _write_fake_lint(project, record_env=False):
    log_path = str(project / "calls.log")
    comp_dir = project / "gen" / "spec-linter"
    comp_dir.mkdir(parents=True, exist_ok=True)
    if record_env:
        body = (
            "import json\n"
            "import os\n"
            "\n"
            "LOG_PATH = " + repr(log_path) + "\n"
            "\n"
            "def main(argv=None):\n"
            "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:\n"
            "        fh.write(json.dumps(os.environ.get(" + repr("VAR_HOTDOCS_CONFIG") + ")) + '\\n')\n"
            "    return 7\n"
        )
    else:
        body = (
            "import json\n"
            "\n"
            "LOG_PATH = " + repr(log_path) + "\n"
            "\n"
            "def main(argv=None):\n"
            "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:\n"
            "        fh.write(json.dumps(argv) + '\\n')\n"
            "    return 7\n"
        )
    (comp_dir / "spec_linter.py").write_text(body, encoding="utf-8")
    return Path(log_path)


def _read_log(log_path):
    if not log_path.is_file():
        return []
    return [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _fake_tool_root(base):
    root = base / "fake-tool-root"
    (root / "gen").mkdir(parents=True, exist_ok=True)
    return root


def test_repo_root_appended_when_absent(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    project = _make_project(tmp_path, "project")
    log_path = _write_fake_lint(project)
    tool_root = _fake_tool_root(tmp_path)
    monkeypatch.chdir(project)

    code = hotdocs_cli.run(["lint", "a.md"], tool_root=str(tool_root), cwd=str(project))

    assert code == 7
    calls = _read_log(log_path)
    assert calls == [["a.md", "--repo-root=" + os.path.abspath(str(project))]]


def test_repo_root_present_forwarded_unchanged(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    project = _make_project(tmp_path, "project")
    log_path = _write_fake_lint(project)
    tool_root = _fake_tool_root(tmp_path)
    elsewhere = _make_project(tmp_path, "elsewhere")
    monkeypatch.chdir(elsewhere)
    proj = str(project)

    code1 = hotdocs_cli.run(["lint", "--repo-root", proj, "a.md"], tool_root=str(tool_root), cwd=str(elsewhere))
    code2 = hotdocs_cli.run(["lint", "--repo-root=" + proj], tool_root=str(tool_root), cwd=str(elsewhere))

    assert code1 == 7
    assert code2 == 7
    calls = _read_log(log_path)
    assert calls == [
        ["--repo-root", proj, "a.md"],
        ["--repo-root=" + proj],
    ]
    for call in calls:
        count = sum(1 for tok in call if tok == "--repo-root" or tok.startswith("--repo-root="))
        assert count == 1


def test_hotdocs_config_env_set_and_restored(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    project = _make_project(tmp_path, "project")
    (project / "hotdocs.toml").write_text("# hotdocs project config\n", encoding="utf-8")
    log_path = _write_fake_lint(project, record_env=True)
    tool_root = _fake_tool_root(tmp_path)
    elsewhere = _make_project(tmp_path, "elsewhere")
    monkeypatch.chdir(elsewhere)
    proj = str(project)

    code1 = hotdocs_cli.run(["lint", "--repo-root", proj], tool_root=str(tool_root), cwd=str(elsewhere))
    assert code1 == 7
    assert "VAR_HOTDOCS_CONFIG" not in os.environ

    monkeypatch.setenv("VAR_HOTDOCS_CONFIG", "/x")
    code2 = hotdocs_cli.run(["lint", "--repo-root", proj], tool_root=str(tool_root), cwd=str(elsewhere))
    assert code2 == 7
    assert os.environ.get("VAR_HOTDOCS_CONFIG") == "/x"

    seen = _read_log(log_path)
    assert len(seen) == 2
    assert seen[0] is not None
    expected = os.path.join(os.path.abspath(proj), "hotdocs.toml")
    assert os.path.normpath(seen[0]) == os.path.normpath(expected)
    assert seen[1] == "/x"