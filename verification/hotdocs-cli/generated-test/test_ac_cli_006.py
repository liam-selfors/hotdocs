# hotdocs-criterion: sha256:ce1911ad49b985faef7caa0b8220923f6d02aaff95526b9262e62eaa8870e2a9
import inspect
from pathlib import Path

import pytest

import hotdocs_cli


def _make_dir(path):
    path.mkdir(parents=True, exist_ok=True)
    return path


def _write_lint_fake(project, body_lines, prelude_lines=()):
    """Write a fake spec-linter component at <project>/gen/spec-linter/spec_linter.py."""
    target_dir = _make_dir(project / "gen" / "spec-linter")
    log_path = str(project / "calls.log")
    source = ""
    source += "import json\n"
    source += "LOG = " + repr(log_path) + "\n"
    for line in prelude_lines:
        source += line + "\n"
    source += "def main(argv):\n"
    source += "    with open(LOG, 'a') as handle:\n"
    source += "        handle.write(json.dumps(argv) + " + repr("\n") + ")\n"
    for line in body_lines:
        source += "    " + line + "\n"
    (target_dir / "spec_linter.py").write_text(source)


def _sink():
    lines = []

    def output_fn(*args, **kwargs):
        lines.append(" ".join(str(a) for a in args))

    return lines, output_fn


def test_routed_verb_exit_codes_zero_then_seven(tmp_path):
    tool_root = _make_dir(tmp_path / "tool-root")

    project_zero = _make_dir(tmp_path / "project-zero")
    _write_lint_fake(project_zero, ["return " + repr(0)])
    _, out0 = _sink()
    code0 = hotdocs_cli.run(
        ["lint"], tool_root=str(tool_root), cwd=str(project_zero), output_fn=out0
    )

    project_seven = _make_dir(tmp_path / "project-seven")
    _write_lint_fake(project_seven, ["return " + repr(7)])
    _, out7 = _sink()
    code7 = hotdocs_cli.run(
        ["lint"], tool_root=str(tool_root), cwd=str(project_seven), output_fn=out7
    )

    assert code0 == 0
    assert code7 == 7


def test_unknown_verb_version_and_missing_component(tmp_path):
    tool_root = _make_dir(tmp_path / "empty-tool-root")
    project = _make_dir(tmp_path / "project")

    _, out_a = _sink()
    code_unknown = hotdocs_cli.run(
        ["frobnicate"], tool_root=str(tool_root), cwd=str(project), output_fn=out_a
    )
    _, out_b = _sink()
    code_version = hotdocs_cli.run(
        ["--version"], tool_root=str(tool_root), cwd=str(project), output_fn=out_b
    )
    _, out_c = _sink()
    code_missing = hotdocs_cli.run(
        ["impact"], tool_root=str(tool_root), cwd=str(project), output_fn=out_c
    )

    assert [code_unknown, code_version, code_missing] == [2, 0, 2]


def test_model_resolution_error_is_usage_error(tmp_path, capsys):
    tool_root = _make_dir(tmp_path / "tool-root")
    project = _make_dir(tmp_path / "project")
    _write_lint_fake(
        project,
        ["raise ModelResolutionError(" + repr("model 'x' names no provider") + ")"],
        prelude_lines=[
            "class ModelResolutionError(Exception):",
            "    pass",
        ],
    )
    capsys.readouterr()
    _, out = _sink()
    code = hotdocs_cli.run(
        ["lint"], tool_root=str(tool_root), cwd=str(project), output_fn=out
    )
    captured = capsys.readouterr()

    assert code == 2
    assert captured.err.splitlines() == ["usage error: model 'x' names no provider"]


def test_other_exception_propagates(tmp_path):
    tool_root = _make_dir(tmp_path / "tool-root")
    project = _make_dir(tmp_path / "project")
    _write_lint_fake(project, ["raise ValueError(" + repr("boom") + ")"])
    _, out = _sink()

    with pytest.raises(ValueError, match="boom"):
        hotdocs_cli.run(
            ["lint"], tool_root=str(tool_root), cwd=str(project), output_fn=out
        )


def test_main_signature_and_version(capsys):
    names = list(inspect.signature(hotdocs_cli.main).parameters)
    assert names == ["argv"]

    capsys.readouterr()
    code = hotdocs_cli.main(["--version"])
    captured = capsys.readouterr()
    lines = captured.out.splitlines()

    assert code == 0
    assert len(lines) == 1
    assert lines[0].startswith("hotdocs ")