import json

import hotdocs_cli


def _write_fake(dest_dir, module_name, return_code, calls_log):
    dest_dir.mkdir(parents=True, exist_ok=True)
    module_path = dest_dir / f"{module_name}.py"
    module_path.write_text(
        "import json\n"
        "\n"
        "def main(argv):\n"
        f"    with open({str(calls_log)!r}, 'a') as fh:\n"
        "        fh.write(json.dumps(argv) + '\\n')\n"
        f"    return {return_code}\n"
    )
    return module_path


def test_lint_routes_to_each_fake_and_returns_its_code(tmp_path):
    project_zero = tmp_path / "proj_zero"
    project_zero.mkdir()
    _write_fake(
        project_zero / "gen" / "spec-linter",
        "spec_linter",
        0,
        project_zero / "calls.log",
    )
    exit_code_zero = hotdocs_cli.main(["lint", "foo"], cwd=str(project_zero))
    assert exit_code_zero == 0

    project_seven = tmp_path / "proj_seven"
    project_seven.mkdir()
    _write_fake(
        project_seven / "gen" / "spec-linter",
        "spec_linter",
        7,
        project_seven / "calls.log",
    )
    exit_code_seven = hotdocs_cli.main(["lint", "foo"], cwd=str(project_seven))
    assert exit_code_seven == 7


def test_unknown_verb_version_and_missing_component_file(tmp_path):
    project = tmp_path / "proj_other"
    project.mkdir()

    unknown_verb_code = hotdocs_cli.main(["frobnicate"], cwd=str(project))
    version_code = hotdocs_cli.main(["--version"], cwd=str(project))
    missing_component_code = hotdocs_cli.main(["impact", "foo"], cwd=str(project))

    assert unknown_verb_code == 2
    assert version_code == 0
    assert missing_component_code == 2