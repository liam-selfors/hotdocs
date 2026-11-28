# hotdocs-criterion: sha256:7374c63c86eb50d9c719cd8ca987c8d7be757d1c8aa2003e6441ed0087f890ad
import json
import os

import hotdocs_cli


def _fake_usage_source(log_path):
    return (
        "import json\n"
        "import sys\n"
        "\n"
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        "\n"
        "def main(argv=None):\n"
        "    with open(LOG_PATH, 'a', encoding='utf-8') as handle:\n"
        "        handle.write(json.dumps(argv) + '\\n')\n"
        "    print('usage error: unknown argument', file=sys.stderr)\n"
        "    print('usage: fake [options]', file=sys.stderr)\n"
        "    return 2\n"
    )


def _fake_ordinary_source(log_path):
    return (
        "import json\n"
        "\n"
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        "\n"
        "def main(argv=None):\n"
        "    with open(LOG_PATH, 'a', encoding='utf-8') as handle:\n"
        "        handle.write(json.dumps(argv) + '\\n')\n"
        "    return 7\n"
    )


def _fake_llm_endpoint_source():
    config = {
        "provider": "claude-cli",
        "model": "sonnet",
        "base_url": None,
        "api_key_env": None,
        "timeout_seconds": None,
        "auth": None,
    }
    return (
        "def load_config(config_path=None):\n"
        "    return " + repr(config) + "\n"
    )


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _make_dirs(tmp_path):
    project = tmp_path / "project"
    tool_root = tmp_path / "toolroot"
    project.mkdir()
    tool_root.mkdir()
    return project, tool_root


def _logged(project):
    log = project / "calls.log"
    if not log.is_file():
        return []
    return [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines() if line.strip()]


def _collector():
    lines = []

    def out(*args, **kwargs):
        lines.append(" ".join(str(a) for a in args))

    return lines, out


def _run(argv, project, tool_root):
    lines, out = _collector()
    code = hotdocs_cli.run(argv, cwd=str(project), tool_root=str(tool_root), output_fn=out)
    return code, lines


def test_lint_help_forwards_and_reformats_usage(tmp_path, capsys):
    project, tool_root = _make_dirs(tmp_path)
    root = os.path.abspath(str(project))
    _write(project / "gen" / "spec-linter" / "spec_linter.py", _fake_usage_source(project / "calls.log"))

    capsys.readouterr()
    code, lines = _run(["lint", "--help"], project, tool_root)
    captured = capsys.readouterr()
    assert code == 0
    assert lines == ["hotdocs lint: validate the spec corpus", "usage: fake [options]"]
    assert captured.err == ""
    assert _logged(project) == [["--help", "--repo-root=" + root]]

    code, lines = _run(["lint", "--strict", "-h"], project, tool_root)
    captured = capsys.readouterr()
    assert code == 0
    assert lines == ["hotdocs lint: validate the spec corpus", "usage: fake [options]"]
    assert captured.err == ""
    assert _logged(project)[-1] == ["--strict", "-h", "--repo-root=" + root]
    assert len(_logged(project)) == 2


def test_generate_and_verify_help_skip_model_injection(tmp_path, capsys):
    project, tool_root = _make_dirs(tmp_path)
    root = os.path.abspath(str(project))
    log = project / "calls.log"
    _write(project / "gen" / "component-gate-runner" / "component_gate_runner.py", _fake_usage_source(log))
    _write(project / "gen" / "provenance-tracker" / "provenance_tracker.py", _fake_usage_source(log))
    _write(project / "gen" / "llm-endpoint" / "llm_endpoint.py", _fake_llm_endpoint_source())

    capsys.readouterr()
    code_gen, lines_gen = _run(["generate", "comp-x", "--help"], project, tool_root)
    err_gen = capsys.readouterr().err
    code_ver, lines_ver = _run(["verify", "--help"], project, tool_root)
    err_ver = capsys.readouterr().err

    assert code_gen == 0
    assert code_ver == 0
    assert lines_gen and lines_gen[0] == "hotdocs generate: generate and verify a component"
    assert lines_ver and lines_ver[0] == "hotdocs verify: is everything ready"
    assert _logged(project) == [
        ["generate", "comp-x", "--help", "--repo-root=" + root],
        ["verify", "--help", "--repo-root=" + root],
    ]
    assert err_gen == ""
    assert err_ver == ""


def test_lint_help_passes_through_component_code(tmp_path, capsys):
    project, tool_root = _make_dirs(tmp_path)
    _write(project / "gen" / "spec-linter" / "spec_linter.py", _fake_ordinary_source(project / "calls.log"))

    code, lines = _run(["lint", "--help"], project, tool_root)
    assert code == 7
    assert lines == []
    assert len(_logged(project)) == 1