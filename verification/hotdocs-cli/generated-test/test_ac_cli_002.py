# hotdocs-criterion: sha256:8e22c2d70905c7b5d0feaca6fbf038005da123d3ec74870f8a718003796a9ede
import json
import os
from pathlib import Path

import hotdocs_cli


def write_fake_lint(project, record_config=False):
    log_path = str(Path(project) / "calls.log")
    base = Path(project) / "gen" / "spec-linter"
    base.mkdir(parents=True, exist_ok=True)
    if record_config:
        body = (
            "    entry = {'argv': list(argv) if argv is not None else None,\n"
            "             'config': os.environ.get('VAR_HOTDOCS_CONFIG')}\n"
        )
    else:
        body = "    entry = list(argv) if argv is not None else None\n"
    source = (
        "import json\n"
        "import os\n"
        "\n"
        "LOG_PATH = " + repr(log_path) + "\n"
        "\n"
        "def main(argv=None):\n"
        + body
        + "    with open(LOG_PATH, 'a', encoding='utf-8') as handle:\n"
        "        handle.write(json.dumps(entry) + '\\n')\n"
        "    return 7\n"
    )
    (base / "spec_linter.py").write_text(source, encoding="utf-8")
    return Path(log_path)


def read_calls(log_path):
    if not log_path.is_file():
        return []
    return [
        json.loads(line)
        for line in log_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def make_tool_root(tmp_path):
    tool_root = tmp_path / "toolroot"
    tool_root.mkdir()
    return tool_root


def test_repo_root_appended_when_absent(tmp_path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    log_path = write_fake_lint(project)
    tool_root = make_tool_root(tmp_path)
    monkeypatch.chdir(project)
    out = []

    code = hotdocs_cli.run(
        ["lint", "a.md"],
        tool_root=tool_root,
        output_fn=out.append,
        cwd=str(project),
    )

    assert code == 7
    calls = read_calls(log_path)
    assert calls == [["a.md", "--repo-root=" + os.path.abspath(str(project))]]


def test_repo_root_separate_token_forwarded_unchanged(tmp_path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    log_path = write_fake_lint(project)
    tool_root = make_tool_root(tmp_path)
    monkeypatch.chdir(project)
    out = []

    code = hotdocs_cli.run(
        ["lint", "--repo-root", str(project), "a.md"],
        tool_root=tool_root,
        output_fn=out.append,
        cwd=str(project),
    )

    assert code == 7
    calls = read_calls(log_path)
    assert calls == [["--repo-root", str(project), "a.md"]]


def test_repo_root_equals_form_forwarded_unchanged(tmp_path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    log_path = write_fake_lint(project)
    tool_root = make_tool_root(tmp_path)
    monkeypatch.chdir(project)
    out = []

    code = hotdocs_cli.run(
        ["lint", "--repo-root=" + str(project)],
        tool_root=tool_root,
        output_fn=out.append,
        cwd=str(project),
    )

    assert code == 7
    calls = read_calls(log_path)
    assert calls == [["--repo-root=" + str(project)]]


def test_config_variable_set_then_respected_then_restored(tmp_path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    (project / "hotdocs.toml").write_text("", encoding="utf-8")
    log_path = write_fake_lint(project, record_config=True)
    tool_root = make_tool_root(tmp_path)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    out = []

    code = hotdocs_cli.run(
        ["lint", "--repo-root", str(project)],
        tool_root=tool_root,
        output_fn=out.append,
        cwd=str(elsewhere),
    )
    assert code == 7
    assert "VAR_HOTDOCS_CONFIG" not in os.environ

    monkeypatch.setenv("VAR_HOTDOCS_CONFIG", "/x")
    code = hotdocs_cli.run(
        ["lint", "--repo-root", str(project)],
        tool_root=tool_root,
        output_fn=out.append,
        cwd=str(elsewhere),
    )
    assert code == 7
    assert os.environ.get("VAR_HOTDOCS_CONFIG") == "/x"

    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)

    calls = read_calls(log_path)
    assert len(calls) == 2
    first, second = calls
    assert first["argv"] == ["--repo-root", str(project)]
    assert first["config"] is not None
    assert Path(first["config"]) == Path(os.path.abspath(str(project))) / "hotdocs.toml"
    assert second["argv"] == ["--repo-root", str(project)]
    assert second["config"] == "/x"
    assert "VAR_HOTDOCS_CONFIG" not in os.environ