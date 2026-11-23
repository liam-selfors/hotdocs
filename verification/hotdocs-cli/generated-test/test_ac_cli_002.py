# hotdocs-criterion: sha256:ff35e9ac5b9b1a084ded6382afe59fbe9482a26f0b67c60feaa335cb3eaef776
import json
import os

import hotdocs_cli


VAR = "VAR_HOTDOCS_CONFIG"


def write_fake_lint(project, record_config=False):
    base = project / "gen" / "spec-linter"
    base.mkdir(parents=True, exist_ok=True)
    log = str(project / "calls.log")
    if record_config:
        line = "json.dumps({'argv': list(argv), 'config': os.environ.get(" + repr(VAR) + ")})"
    else:
        line = "json.dumps(list(argv))"
    source = (
        "import json\n"
        "import os\n"
        "\n"
        "def main(argv=None):\n"
        "    with open(" + repr(log) + ", 'a', encoding='utf-8') as handle:\n"
        "        handle.write(" + line + " + '\\n')\n"
        "    return 7\n"
    )
    (base / "spec_linter.py").write_text(source, encoding="utf-8")


def read_calls(project):
    path = project / "calls.log"
    if not path.is_file():
        return []
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def make_dirs(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    tool_root = tmp_path / "toolroot"
    tool_root.mkdir()
    return project, tool_root


def quiet(*args, **kwargs):
    return None


def test_repo_root_appended_when_absent(tmp_path, monkeypatch):
    project, tool_root = make_dirs(tmp_path)
    write_fake_lint(project)
    monkeypatch.delenv(VAR, raising=False)

    code = hotdocs_cli.run(
        ["lint", "a.md"],
        tool_root=str(tool_root),
        output_fn=quiet,
        cwd=str(project),
    )

    assert code == 7
    root = os.path.abspath(str(project))
    assert read_calls(project) == [["a.md", "--repo-root=" + root]]


def test_repo_root_separate_value_forwarded_unchanged(tmp_path, monkeypatch):
    project, tool_root = make_dirs(tmp_path)
    write_fake_lint(project)
    monkeypatch.delenv(VAR, raising=False)

    code = hotdocs_cli.run(
        ["lint", "--repo-root", str(project), "a.md"],
        tool_root=str(tool_root),
        output_fn=quiet,
        cwd=str(project),
    )

    assert code == 7
    calls = read_calls(project)
    assert calls == [["--repo-root", str(project), "a.md"]]
    assert sum(1 for t in calls[0] if t.startswith("--repo-root")) == 1


def test_repo_root_equals_form_forwarded_unchanged(tmp_path, monkeypatch):
    project, tool_root = make_dirs(tmp_path)
    write_fake_lint(project)
    monkeypatch.delenv(VAR, raising=False)

    code = hotdocs_cli.run(
        ["lint", "--repo-root=" + str(project)],
        tool_root=str(tool_root),
        output_fn=quiet,
        cwd=str(project),
    )

    assert code == 7
    calls = read_calls(project)
    assert calls == [["--repo-root=" + str(project)]]
    assert sum(1 for t in calls[0] if t.startswith("--repo-root")) == 1


def test_config_variable_set_and_restored(tmp_path, monkeypatch):
    project, tool_root = make_dirs(tmp_path)
    (project / "hotdocs.toml").write_text("", encoding="utf-8")
    write_fake_lint(project, record_config=True)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(str(elsewhere))
    monkeypatch.delenv(VAR, raising=False)

    root = os.path.abspath(str(project))
    expected_config = os.path.join(root, "hotdocs.toml")

    code = hotdocs_cli.run(
        ["lint", "--repo-root", str(project)],
        tool_root=str(tool_root),
        output_fn=quiet,
        cwd=str(elsewhere),
    )
    assert code == 7
    assert VAR not in os.environ

    monkeypatch.setenv(VAR, "/x")
    code = hotdocs_cli.run(
        ["lint", "--repo-root", str(project)],
        tool_root=str(tool_root),
        output_fn=quiet,
        cwd=str(elsewhere),
    )
    assert code == 7
    assert os.environ.get(VAR) == "/x"

    calls = read_calls(project)
    assert len(calls) == 2
    first, second = calls
    assert first["argv"] == ["--repo-root", str(project)]
    assert first["config"] is not None
    assert os.path.normpath(first["config"]) == os.path.normpath(expected_config)
    assert second["argv"] == ["--repo-root", str(project)]
    assert second["config"] == "/x"

    monkeypatch.delenv(VAR, raising=False)
    assert VAR not in os.environ