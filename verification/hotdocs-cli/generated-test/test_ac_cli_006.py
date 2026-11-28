# hotdocs-criterion: sha256:4b8e1ce25ded442bbea5477552b06c67abdbdc6cd91767420ef46d4b37d4bb86
import inspect
import json

import pytest

import hotdocs_cli


def _write_lint_fake(project, body_lines):
    """Write a fake spec-linter component at <project>/gen/spec-linter/spec_linter.py.

    body_lines are the statements of main after the call has been logged.
    """
    target_dir = project / "gen" / "spec-linter"
    target_dir.mkdir(parents=True, exist_ok=True)
    log_path = str(project / "calls.log")
    source = (
        "import json\n"
        "import sys\n"
        "\n"
        "\n"
        "class ModelResolutionError(Exception):\n"
        "    pass\n"
        "\n"
        "\n"
        "def main(argv=None):\n"
        "    with open(" + repr(log_path) + ", 'a', encoding='utf-8') as fh:\n"
        "        fh.write(json.dumps(argv) + '\\n')\n"
    )
    for line in body_lines:
        source += "    " + line + "\n"
    (target_dir / "spec_linter.py").write_text(source, encoding="utf-8")
    return project / "calls.log"


def _read_calls(log_path):
    if not log_path.is_file():
        return []
    return [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]


@pytest.fixture
def empty_tool_root(tmp_path):
    root = tmp_path / "empty_tool_root"
    root.mkdir()
    return root


def test_routed_lint_returns_component_exit_codes(tmp_path, empty_tool_root):
    project_a = tmp_path / "project_a"
    project_a.mkdir()
    log_a = _write_lint_fake(project_a, ["return " + repr(0)])

    project_b = tmp_path / "project_b"
    project_b.mkdir()
    log_b = _write_lint_fake(project_b, ["return " + repr(7)])

    out = []
    code_a = hotdocs_cli.run(
        ["lint"], cwd=str(project_a), tool_root=str(empty_tool_root), output_fn=out.append
    )
    code_b = hotdocs_cli.run(
        ["lint"], cwd=str(project_b), tool_root=str(empty_tool_root), output_fn=out.append
    )

    assert code_a == 0
    assert code_b == 7
    # Confirm each fake actually ran (tokens themselves are not asserted).
    assert len(_read_calls(log_a)) == 1
    assert len(_read_calls(log_b)) == 1


def test_unknown_verb_version_and_missing_component(tmp_path, empty_tool_root):
    project = tmp_path / "project"
    project.mkdir()
    out = []

    code_unknown = hotdocs_cli.run(
        ["frobnicate"], cwd=str(project), tool_root=str(empty_tool_root), output_fn=out.append
    )
    code_version = hotdocs_cli.run(
        ["--version"], cwd=str(project), tool_root=str(empty_tool_root), output_fn=out.append
    )
    code_missing = hotdocs_cli.run(
        ["lint"], cwd=str(project), tool_root=str(empty_tool_root), output_fn=out.append
    )

    assert code_unknown == 2
    assert code_version == 0
    assert code_missing == 2


def test_model_resolution_error_is_usage_error(tmp_path, empty_tool_root, capsys):
    project = tmp_path / "project"
    project.mkdir()
    log_path = _write_lint_fake(
        project, ["raise ModelResolutionError(" + repr("model 'x' names no provider") + ")"]
    )

    out = []
    capsys.readouterr()
    code = hotdocs_cli.run(
        ["lint"], cwd=str(project), tool_root=str(empty_tool_root), output_fn=out.append
    )
    captured = capsys.readouterr()

    assert code == 2
    assert captured.err.splitlines() == ["usage error: model 'x' names no provider"]
    assert len(_read_calls(log_path)) == 1


def test_other_exception_propagates(tmp_path, empty_tool_root):
    project = tmp_path / "project"
    project.mkdir()
    log_path = _write_lint_fake(project, ["raise ValueError(" + repr("boom") + ")"])

    out = []
    with pytest.raises(ValueError, match="boom"):
        hotdocs_cli.run(
            ["lint"], cwd=str(project), tool_root=str(empty_tool_root), output_fn=out.append
        )
    assert len(_read_calls(log_path)) == 1


def test_main_signature_and_version(capsys):
    params = list(inspect.signature(hotdocs_cli.main).parameters)
    assert params == ["argv"]

    capsys.readouterr()
    code = hotdocs_cli.main(["--version"])
    captured = capsys.readouterr()

    assert code == 0
    lines = captured.out.splitlines()
    assert len(lines) == 1
    assert lines[0].startswith("hotdocs ")