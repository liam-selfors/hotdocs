# hotdocs-criterion: sha256:c83a6bb90291725db23832c53e90aa3c7647d89023968b7cda2d6faa3fe8ea19
import json
import os

import hotdocs_cli


def _fake_source(log_path, usage):
    source = (
        "import json\n"
        "import sys\n"
        "\n"
        "LOG = " + repr(str(log_path)) + "\n"
        "\n"
        "\n"
        "def main(argv=None):\n"
        "    with open(LOG, 'a', encoding='utf-8') as handle:\n"
        "        handle.write(json.dumps(list(argv)) + chr(10))\n"
    )
    if usage:
        source += (
            "    print(" + repr("usage error: unknown argument") + ", file=sys.stderr)\n"
            "    print(" + repr("usage: fake [options]") + ", file=sys.stderr)\n"
            "    return 2\n"
        )
    else:
        source += "    return 7\n"
    return source


def _write_fake(project, rel_dir, module, usage):
    directory = project / rel_dir
    directory.mkdir(parents=True, exist_ok=True)
    (directory / (module + ".py")).write_text(
        _fake_source(project / "calls.log", usage), encoding="utf-8"
    )


def _write_fake_llm_endpoint(project, config):
    directory = project / "gen" / "llm-endpoint"
    directory.mkdir(parents=True, exist_ok=True)
    source = (
        "def load_config(config_path=None):\n"
        "    return " + repr(config) + "\n"
    )
    (directory / "llm_endpoint.py").write_text(source, encoding="utf-8")


def _calls(project):
    log = project / "calls.log"
    if not log.is_file():
        return []
    return [
        json.loads(line)
        for line in log.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _make_dirs(tmp_path, name):
    project = tmp_path / name
    project.mkdir()
    tool_root = tmp_path / (name + "-tool-root")
    tool_root.mkdir()
    return project, tool_root


def _run(argv, project, tool_root):
    lines = []

    def collector(line):
        lines.append(line)

    code = hotdocs_cli.run(
        argv, cwd=str(project), tool_root=str(tool_root), output_fn=collector
    )
    return code, lines


def test_lint_help_with_usage_component(tmp_path, capsys):
    project, tool_root = _make_dirs(tmp_path, "project")
    _write_fake(project, "gen/spec-linter", "spec_linter", usage=True)
    root = os.path.abspath(str(project))

    code, lines = _run(["lint", "--help"], project, tool_root)
    captured = capsys.readouterr()
    assert code == 0
    assert lines == [
        "hotdocs lint: validate the spec corpus",
        "usage: fake [options]",
    ]
    assert captured.err == ""
    calls = _calls(project)
    assert len(calls) == 1
    assert calls[0] == ["--help", "--repo-root=" + root]

    code, lines = _run(["lint", "--strict", "-h"], project, tool_root)
    captured = capsys.readouterr()
    assert code == 0
    assert lines == [
        "hotdocs lint: validate the spec corpus",
        "usage: fake [options]",
    ]
    assert captured.err == ""
    calls = _calls(project)
    assert len(calls) == 2
    assert calls[1] == ["--strict", "-h", "--repo-root=" + root]


def test_generate_and_verify_help(tmp_path, capsys):
    project, tool_root = _make_dirs(tmp_path, "project")
    _write_fake(
        project, "gen/component-gate-runner", "component_gate_runner", usage=True
    )
    _write_fake(project, "gen/provenance-tracker", "provenance_tracker", usage=True)
    _write_fake_llm_endpoint(
        project,
        {
            "provider": "claude-cli",
            "model": "sonnet",
            "base_url": None,
            "api_key_env": None,
            "timeout_seconds": None,
            "auth": None,
        },
    )
    root = os.path.abspath(str(project))

    code, lines = _run(["generate", "comp-x", "--help"], project, tool_root)
    captured = capsys.readouterr()
    assert code == 0
    assert lines
    assert lines[0] == "hotdocs generate: generate and verify a component"
    assert captured.err == ""
    calls = _calls(project)
    assert len(calls) == 1
    assert calls[0] == ["generate", "comp-x", "--help", "--repo-root=" + root]

    code, lines = _run(["verify", "--help"], project, tool_root)
    captured = capsys.readouterr()
    assert code == 0
    assert lines
    assert lines[0] == "hotdocs verify: is everything ready"
    assert captured.err == ""
    calls = _calls(project)
    assert len(calls) == 2
    assert calls[1] == ["verify", "--help", "--repo-root=" + root]


def test_lint_help_with_ordinary_component_passes_code_through(tmp_path, capsys):
    project, tool_root = _make_dirs(tmp_path, "project")
    _write_fake(project, "gen/spec-linter", "spec_linter", usage=False)

    code, lines = _run(["lint", "--help"], project, tool_root)
    capsys.readouterr()
    assert code == 7
    assert lines == []