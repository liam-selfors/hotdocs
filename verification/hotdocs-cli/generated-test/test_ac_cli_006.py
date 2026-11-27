# hotdocs-criterion: sha256:bb18484ab9b9e073cbe7eb8c7858519d9e0fce38afd9a53b1839373564b6325f
import inspect
import json
from pathlib import Path

import pytest

import hotdocs_cli


def _make_dirs(tmp_path, name):
    project = tmp_path / (name + "-project")
    project.mkdir()
    tool_root = tmp_path / (name + "-toolroot")
    tool_root.mkdir()
    return project, tool_root


def _log_lines(source_lines, log_path):
    # Lines of source that append json.dumps(argv) to the log file.
    return source_lines + [
        "    with open(" + repr(str(log_path)) + ", 'a') as handle:\n",
        "        handle.write(json.dumps(argv) + '\\n')\n",
    ]


def _write_lint_fake(project, body_lines, preamble_lines=None):
    directory = project / "gen" / "spec-linter"
    directory.mkdir(parents=True, exist_ok=True)
    log_path = project / "calls.log"
    lines = ["import json\n"]
    if preamble_lines:
        lines.extend(preamble_lines)
    lines.append("def main(argv):\n")
    lines = _log_lines(lines, log_path)
    lines.extend(body_lines)
    (directory / "spec_linter.py").write_text("".join(lines), encoding="utf-8")
    return log_path


def _read_log(log_path):
    if not log_path.is_file():
        return []
    return [line for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _sink():
    collected = []

    def output_fn(*args, **kwargs):
        collected.append(" ".join(str(a) for a in args))

    return collected, output_fn


def test_routed_lint_returns_component_exit_codes(tmp_path):
    codes = []
    for index, code in enumerate([0, 7]):
        project, tool_root = _make_dirs(tmp_path, "route" + repr(index))
        log_path = _write_lint_fake(project, ["    return " + repr(code) + "\n"])
        _, output_fn = _sink()
        result = hotdocs_cli.run(
            ["lint"],
            tool_root=str(tool_root),
            output_fn=output_fn,
            cwd=str(project),
        )
        codes.append(result)
        assert len(_read_log(log_path)) == 1
    assert codes == [0, 7]


def test_unknown_verb_version_and_missing_component_exit_codes(tmp_path):
    project, tool_root = _make_dirs(tmp_path, "codes")
    _, output_fn = _sink()

    unknown = hotdocs_cli.run(
        ["frobnicate"],
        tool_root=str(tool_root),
        output_fn=output_fn,
        cwd=str(project),
    )
    version = hotdocs_cli.run(
        ["--version"],
        tool_root=str(tool_root),
        output_fn=output_fn,
        cwd=str(project),
    )
    missing = hotdocs_cli.run(
        ["lint"],
        tool_root=str(tool_root),
        output_fn=output_fn,
        cwd=str(project),
    )
    assert [unknown, version, missing] == [2, 0, 2]


def test_model_resolution_error_by_class_name_is_usage_error(tmp_path, capsys):
    project, tool_root = _make_dirs(tmp_path, "mre")
    message = "model 'x' names no provider"
    log_path = _write_lint_fake(
        project,
        ["    raise ModelResolutionError(" + repr(message) + ")\n"],
        preamble_lines=[
            "class ModelResolutionError(Exception):\n",
            "    pass\n",
        ],
    )
    _, output_fn = _sink()
    capsys.readouterr()
    result = hotdocs_cli.run(
        ["lint"],
        tool_root=str(tool_root),
        output_fn=output_fn,
        cwd=str(project),
    )
    captured = capsys.readouterr()
    assert result == 2
    assert captured.err.splitlines() == ["usage error: " + message]
    assert len(_read_log(log_path)) == 1


def test_other_exception_propagates(tmp_path):
    project, tool_root = _make_dirs(tmp_path, "valueerror")
    _write_lint_fake(project, ["    raise ValueError(" + repr("boom") + ")\n"])
    _, output_fn = _sink()
    with pytest.raises(ValueError, match="boom"):
        hotdocs_cli.run(
            ["lint"],
            tool_root=str(tool_root),
            output_fn=output_fn,
            cwd=str(project),
        )


def test_main_signature_and_version(capsys):
    names = list(inspect.signature(hotdocs_cli.main).parameters)
    assert names == ["argv"]

    capsys.readouterr()
    result = hotdocs_cli.main(["--version"])
    captured = capsys.readouterr()
    assert result == 0
    lines = captured.out.splitlines()
    assert len(lines) == 1
    assert lines[0].startswith("hotdocs ")