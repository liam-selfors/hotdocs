# hotdocs-criterion: sha256:719231bc62d85bdf975eb53b9a4524728c0e22a687fa197e4ad86a1bb3bb8eca
import inspect
import json
from pathlib import Path

import pytest

import hotdocs_cli


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _make_project(tmp_path, name):
    project = tmp_path / name
    project.mkdir(parents=True, exist_ok=True)
    return project


def _empty_tool_root(tmp_path, name="toolroot"):
    root = tmp_path / name
    root.mkdir(parents=True, exist_ok=True)
    return root


def _fake_linter_returning(project, code):
    log_path = str(project / "calls.log")
    source = "\n".join([
        "import json",
        "",
        "def main(argv=None):",
        "    with open(" + repr(log_path) + ", 'a', encoding='utf-8') as handle:",
        "        handle.write(json.dumps(argv) + '\\n')",
        "    return " + repr(code),
        "",
    ])
    _write(project / "gen" / "spec-linter" / "spec_linter.py", source)


def _fake_linter_raising(project, raise_lines):
    log_path = str(project / "calls.log")
    lines = [
        "import json",
        "",
        "class ModelResolutionError(Exception):",
        "    pass",
        "",
        "def main(argv=None):",
        "    with open(" + repr(log_path) + ", 'a', encoding='utf-8') as handle:",
        "        handle.write(json.dumps(argv) + '\\n')",
    ]
    lines.extend(raise_lines)
    lines.append("")
    _write(project / "gen" / "spec-linter" / "spec_linter.py", "\n".join(lines))


def _read_calls(project):
    log = project / "calls.log"
    if not log.is_file():
        return []
    return [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_routed_verb_returns_component_codes_zero_then_seven(tmp_path):
    tool_root = _empty_tool_root(tmp_path)

    project_zero = _make_project(tmp_path, "project_zero")
    _fake_linter_returning(project_zero, 0)
    code_zero = hotdocs_cli.run(["lint"], tool_root=str(tool_root), cwd=str(project_zero))

    project_seven = _make_project(tmp_path, "project_seven")
    _fake_linter_returning(project_seven, 7)
    code_seven = hotdocs_cli.run(["lint"], tool_root=str(tool_root), cwd=str(project_seven))

    assert code_zero == 0
    assert code_seven == 7
    assert len(_read_calls(project_zero)) == 1
    assert len(_read_calls(project_seven)) == 1


def test_unknown_verb_version_and_missing_component_codes(tmp_path):
    tool_root = _empty_tool_root(tmp_path)
    project = _make_project(tmp_path, "project_missing")
    outputs = []

    def capture(*args, **kwargs):
        outputs.append(" ".join(str(a) for a in args))

    code_unknown = hotdocs_cli.run(
        ["frobnicate"], tool_root=str(tool_root), cwd=str(project), output_fn=capture
    )
    code_version = hotdocs_cli.run(
        ["--version"], tool_root=str(tool_root), cwd=str(project), output_fn=capture
    )
    code_missing = hotdocs_cli.run(
        ["lint"], tool_root=str(tool_root), cwd=str(project), output_fn=capture
    )

    assert code_unknown == 2
    assert code_version == 0
    assert code_missing == 2


def test_model_resolution_error_by_class_name_is_usage_error(tmp_path, capsys):
    tool_root = _empty_tool_root(tmp_path)
    project = _make_project(tmp_path, "project_mre")
    _fake_linter_raising(project, [
        "    raise ModelResolutionError(" + repr("model 'x' names no provider") + ")",
    ])
    capsys.readouterr()

    code = hotdocs_cli.run(["lint"], tool_root=str(tool_root), cwd=str(project))

    captured = capsys.readouterr()
    assert code == 2
    lines = [line for line in captured.err.splitlines() if line.strip()]
    assert lines == ["usage error: model 'x' names no provider"]
    assert "Traceback" not in captured.err
    assert len(_read_calls(project)) == 1


def test_other_exception_propagates(tmp_path):
    tool_root = _empty_tool_root(tmp_path)
    project = _make_project(tmp_path, "project_valueerror")
    _fake_linter_raising(project, [
        "    raise ValueError(" + repr("boom") + ")",
    ])

    with pytest.raises(ValueError) as excinfo:
        hotdocs_cli.run(["lint"], tool_root=str(tool_root), cwd=str(project))

    assert "boom" in str(excinfo.value)
    assert len(_read_calls(project)) == 1


def test_main_signature_and_version(capsys):
    params = list(inspect.signature(hotdocs_cli.main).parameters)
    assert params == ["argv"]

    capsys.readouterr()
    code = hotdocs_cli.main(["--version"])
    captured = capsys.readouterr()

    assert code == 0
    out_lines = [line.strip() for line in captured.out.splitlines() if line.strip()]
    assert "hotdocs 0.1.0" in out_lines