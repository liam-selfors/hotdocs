# hotdocs-criterion: sha256:c05a2b7058e3a381b1e0da2d15fd0e19c00cfa3c6118bdfc474d7494479b7264
import inspect
import os

import pytest

import hotdocs_cli


def _write_fake_linter(project, body_lines):
    """Write a fake spec-linter component under <project>/gen/spec-linter/spec_linter.py.

    The fake's main logs its argv to <project>/calls.log, then runs body_lines.
    """
    target_dir = os.path.join(str(project), "gen", "spec-linter")
    os.makedirs(target_dir, exist_ok=True)
    log_path = os.path.join(str(project), "calls.log")
    source = (
        "import json\n"
        "\n"
        "LOG_PATH = " + repr(log_path) + "\n"
        "\n"
        "\n"
        "class ModelResolutionError(Exception):\n"
        "    pass\n"
        "\n"
        "\n"
        "def main(argv=None):\n"
        "    with open(LOG_PATH, 'a', encoding='utf-8') as handle:\n"
        "        handle.write(json.dumps(argv) + '\\n')\n"
    )
    for line in body_lines:
        source += "    " + line + "\n"
    path = os.path.join(target_dir, "spec_linter.py")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(source)
    return path


def _make_dirs(tmp_path, name):
    project = tmp_path / (name + "-project")
    tool_root = tmp_path / (name + "-tool-root")
    project.mkdir()
    tool_root.mkdir()
    return project, tool_root


def _run(argv, project, tool_root, outputs):
    def output_fn(*args, **kwargs):
        outputs.append(" ".join(str(a) for a in args))

    return hotdocs_cli.run(
        argv,
        tool_root=str(tool_root),
        output_fn=output_fn,
        env={},
        cwd=str(project),
    )


def test_routed_verb_returns_component_codes_zero_then_seven(tmp_path):
    project_a, tool_root_a = _make_dirs(tmp_path, "zero")
    _write_fake_linter(project_a, ["return 0"])
    outputs = []
    code_a = _run(["lint"], project_a, tool_root_a, outputs)

    project_b, tool_root_b = _make_dirs(tmp_path, "seven")
    _write_fake_linter(project_b, ["return 7"])
    code_b = _run(["lint"], project_b, tool_root_b, outputs)

    assert code_a == 0
    assert code_b == 7


def test_unknown_verb_version_and_missing_component_exit_codes(tmp_path):
    project, tool_root = _make_dirs(tmp_path, "codes")
    outputs = []

    code_unknown = _run(["frobnicate"], project, tool_root, outputs)
    code_version = _run(["--version"], project, tool_root, outputs)
    code_missing = _run(["lint"], project, tool_root, outputs)

    assert [code_unknown, code_version, code_missing] == [2, 0, 2]


def test_model_resolution_error_by_class_name_is_usage_error(tmp_path, capsys):
    project, tool_root = _make_dirs(tmp_path, "mre")
    _write_fake_linter(
        project,
        ["raise ModelResolutionError(" + repr("model 'x' names no provider") + ")"],
    )
    capsys.readouterr()
    outputs = []
    code = _run(["lint"], project, tool_root, outputs)
    captured = capsys.readouterr()

    assert code == 2
    assert captured.err.splitlines() == ["usage error: model 'x' names no provider"]


def test_other_exception_propagates(tmp_path):
    project, tool_root = _make_dirs(tmp_path, "valueerror")
    _write_fake_linter(project, ["raise ValueError(" + repr("boom") + ")"])
    outputs = []

    with pytest.raises(ValueError, match="boom"):
        _run(["lint"], project, tool_root, outputs)


def test_main_takes_only_argv_and_prints_version(capsys):
    names = list(inspect.signature(hotdocs_cli.main).parameters)
    assert names == ["argv"]

    capsys.readouterr()
    code = hotdocs_cli.main(["--version"])
    captured = capsys.readouterr()

    lines = captured.out.splitlines()
    assert len(lines) == 1
    assert lines[0].startswith("hotdocs ")
    assert code == 0