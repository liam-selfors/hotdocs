# hotdocs-criterion: sha256:40b3ecced344961b32ccffa2fe697e6e1586a8146e2ea268be332ee9515dacfe
import json
import os
import sys
from pathlib import Path

import hotdocs_cli


def _write_fake_component(project, rel_dir, module, usage):
    d = Path(project) / rel_dir
    d.mkdir(parents=True, exist_ok=True)
    log_path = str(Path(project) / "calls.log")
    src = (
        "import json\n"
        "import sys\n"
        "\n"
        "LOG = " + repr(log_path) + "\n"
        "\n"
        "def main(argv=None):\n"
        "    with open(LOG, 'a', encoding='utf-8') as f:\n"
        "        f.write(json.dumps(argv) + " + repr("\n") + ")\n"
    )
    if usage:
        src += (
            "    print(" + repr("usage error: unknown argument") + ", file=sys.stderr)\n"
            "    print(" + repr("usage: fake [options]") + ", file=sys.stderr)\n"
            "    return 2\n"
        )
    else:
        src += "    return 7\n"
    (d / (module + ".py")).write_text(src, encoding="utf-8")


def _write_fake_llm_endpoint(project):
    d = Path(project) / "gen" / "llm-endpoint"
    d.mkdir(parents=True, exist_ok=True)
    config = {
        "provider": "claude-cli",
        "model": "sonnet",
        "base_url": None,
        "api_key_env": None,
        "timeout_seconds": None,
        "auth": None,
    }
    src = (
        "def load_config(config_path=None):\n"
        "    return " + repr(config) + "\n"
    )
    (d / "llm_endpoint.py").write_text(src, encoding="utf-8")


def _calls(project):
    log = Path(project) / "calls.log"
    if not log.is_file():
        return []
    return [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines() if line.strip()]


def _make_dirs(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    tool_root = tmp_path / "toolroot"
    tool_root.mkdir()
    return project, tool_root


def _collector():
    lines = []

    def output_fn(*args, **kwargs):
        lines.append(" ".join(str(a) for a in args))

    return lines, output_fn


def test_lint_help_reports_verb_summary_and_usage(tmp_path, capsys):
    project, tool_root = _make_dirs(tmp_path)
    _write_fake_component(project, "gen/spec-linter", "spec_linter", usage=True)
    root = os.path.abspath(str(project))

    lines, out = _collector()
    capsys.readouterr()
    code = hotdocs_cli.run(["lint", "--help"], tool_root=str(tool_root), output_fn=out, cwd=str(project))
    captured = capsys.readouterr()
    assert code == 0
    assert lines == ["hotdocs lint: validate the spec corpus", "usage: fake [options]"]
    assert captured.err == ""
    calls = _calls(project)
    assert len(calls) == 1
    assert calls[-1] == ["--help", "--repo-root=" + root]

    lines2, out2 = _collector()
    code2 = hotdocs_cli.run(["lint", "--strict", "-h"], tool_root=str(tool_root), output_fn=out2, cwd=str(project))
    captured2 = capsys.readouterr()
    assert code2 == 0
    assert lines2 == ["hotdocs lint: validate the spec corpus", "usage: fake [options]"]
    assert captured2.err == ""
    calls = _calls(project)
    assert len(calls) == 2
    assert calls[-1] == ["--strict", "-h", "--repo-root=" + root]


def test_generate_and_verify_help_skip_model_handling(tmp_path, capsys):
    project, tool_root = _make_dirs(tmp_path)
    _write_fake_component(project, "gen/component-gate-runner", "component_gate_runner", usage=True)
    _write_fake_component(project, "gen/provenance-tracker", "provenance_tracker", usage=True)
    _write_fake_llm_endpoint(project)
    root = os.path.abspath(str(project))

    capsys.readouterr()
    lines, out = _collector()
    code = hotdocs_cli.run(["generate", "comp-x", "--help"], tool_root=str(tool_root), output_fn=out, cwd=str(project))
    captured = capsys.readouterr()
    assert code == 0
    assert lines
    assert lines[0] == "hotdocs generate: generate and verify a component"
    assert captured.err == ""
    calls = _calls(project)
    assert len(calls) == 1
    assert calls[-1] == ["generate", "comp-x", "--help", "--repo-root=" + root]

    lines2, out2 = _collector()
    code2 = hotdocs_cli.run(["verify", "--help"], tool_root=str(tool_root), output_fn=out2, cwd=str(project))
    captured2 = capsys.readouterr()
    assert code2 == 0
    assert lines2
    assert lines2[0] == "hotdocs verify: is everything ready"
    assert captured2.err == ""
    calls = _calls(project)
    assert len(calls) == 2
    assert calls[-1] == ["verify", "--help", "--repo-root=" + root]


def test_ordinary_component_code_passed_through_on_help(tmp_path, capsys):
    project, tool_root = _make_dirs(tmp_path)
    _write_fake_component(project, "gen/spec-linter", "spec_linter", usage=False)

    lines, out = _collector()
    code = hotdocs_cli.run(["lint", "--help"], tool_root=str(tool_root), output_fn=out, cwd=str(project))
    assert code == 7
    assert lines == []