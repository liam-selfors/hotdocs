from pathlib import Path

import hotdocs_cli


def _write_fake_component(project, dir_parts, module_name, calls_log, return_code):
    component_dir = Path(project)
    for part in dir_parts:
        component_dir = component_dir / part
    component_dir.mkdir(parents=True, exist_ok=True)
    module_path = component_dir / f"{module_name}.py"
    module_path.write_text(
        "import json\n\n"
        "def main(argv):\n"
        f"    with open({str(calls_log)!r}, \"a\") as handle:\n"
        "        handle.write(json.dumps(argv) + \"\\n\")\n"
        f"    return {return_code}\n"
    )


def test_main_routes_lint_to_each_fake(tmp_path):
    project_zero = tmp_path / "project-zero"
    project_zero.mkdir()
    calls_log_zero = project_zero / "calls.log"
    _write_fake_component(
        project_zero, ("gen", "spec-linter"), "spec_linter", calls_log_zero, 0
    )
    assert hotdocs_cli.main(["lint"], cwd=str(project_zero)) == 0

    project_seven = tmp_path / "project-seven"
    project_seven.mkdir()
    calls_log_seven = project_seven / "calls.log"
    _write_fake_component(
        project_seven, ("gen", "spec-linter"), "spec_linter", calls_log_seven, 7
    )
    assert hotdocs_cli.main(["lint"], cwd=str(project_seven)) == 7


def test_main_exit_codes_for_unknown_verb_version_and_missing_component(tmp_path):
    project = tmp_path / "project"
    project.mkdir()

    assert hotdocs_cli.main(["frobnicate"], cwd=str(project)) == 2
    assert hotdocs_cli.main(["--version"], cwd=str(project)) == 0

    empty_tool_root = tmp_path / "empty-tool-root"
    empty_tool_root.mkdir()
    assert (
        hotdocs_cli.main(
            ["impact"], cwd=str(project), tool_root=str(empty_tool_root)
        )
        == 2
    )