import hotdocs_cli


VERB_SUMMARIES = {
    "lint": "validate the spec corpus",
    "impact": "blast radius of a change",
    "assemble": "build a component's spec bundle",
    "compile-criteria": "compile the compiled criteria",
    "author-test": "write one criterion's test",
    "verify-component": "verify one component",
    "generate": "generate and verify a component",
    "verify": "is everything ready",
    "track feedback": "last failing requirements",
    "track ui build": "build the readiness page",
    "provenance check": "is provenance a hit",
    "provenance write": "write a provenance manifest",
    "license-scan": "license scan one component",
    "secret-scan": "scan for secrets",
    "review-packet build": "build a review packet",
    "decision-drift": "decisions out of step with specs",
    "decision-impact": "what a decision touches",
    "docs-site build": "render the docs site",
    "corpus-graph build": "build the corpus graph",
    "assist": "review a spec change",
    "init": "set up a new project",
}


def _collecting_output():
    lines = []

    def output_fn(msg=""):
        lines.append(str(msg))

    return lines, output_fn


def _assert_full_help_text(text):
    assert "hotdocs 0.1.0" in text
    for verb, summary in VERB_SUMMARIES.items():
        assert verb in text
        assert summary in text


def test_help_variants_print_version_and_full_verb_table(tmp_path):
    for argv in ([], ["--help"], ["-h"], ["help"]):
        lines, output_fn = _collecting_output()
        rc = hotdocs_cli.main(
            list(argv), tool_root=tmp_path, output_fn=output_fn, cwd=tmp_path
        )
        assert rc == 0
        _assert_full_help_text("\n".join(lines))


def test_version_flag_prints_version_and_returns_zero(tmp_path):
    lines, output_fn = _collecting_output()
    rc = hotdocs_cli.main(
        ["--version"], tool_root=tmp_path, output_fn=output_fn, cwd=tmp_path
    )
    assert rc == 0
    assert "hotdocs 0.1.0" in "\n".join(lines)


def test_unknown_verb_returns_two_and_lists_verbs_on_stderr(tmp_path, capsys):
    rc = hotdocs_cli.main(["frobnicate"], tool_root=tmp_path, cwd=tmp_path)
    assert rc == 2
    err = capsys.readouterr().err
    assert "unknown verb: frobnicate" in err
    for verb in VERB_SUMMARIES:
        assert verb in err


def test_lint_missing_under_both_project_and_tool_root_names_path(tmp_path, capsys):
    project = tmp_path / "project"
    project.mkdir()
    fake_tool_root = tmp_path / "fake_tool_root"
    fake_tool_root.mkdir()

    rc = hotdocs_cli.main(["lint"], tool_root=fake_tool_root, cwd=project)

    assert rc == 2
    err = capsys.readouterr().err
    lines = [line for line in err.splitlines() if line.strip()]
    assert lines
    assert "gen/spec-linter/spec_linter.py" in lines[0]


def test_lint_component_with_no_main_returns_two(tmp_path, capsys):
    project = tmp_path / "project_no_main"
    project.mkdir()
    gen_dir = project / "gen" / "spec-linter"
    gen_dir.mkdir(parents=True)
    (gen_dir / "spec_linter.py").write_text("value = 1\n")

    unused_tool_root = tmp_path / "unused_tool_root"
    unused_tool_root.mkdir()

    rc = hotdocs_cli.main(["lint"], tool_root=unused_tool_root, cwd=project)

    assert rc == 2