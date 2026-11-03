import pytest

import hotdocs_cli


VERB_TABLE = [
    ("lint", "validate the spec corpus"),
    ("impact", "blast radius of a change"),
    ("assemble", "build a component's spec bundle"),
    ("compile-criteria", "compile the compiled criteria"),
    ("author-test", "write one criterion's test"),
    ("verify-component", "verify one component"),
    ("generate", "generate and verify a component"),
    ("verify", "is everything ready"),
    ("track feedback", "last failing requirements"),
    ("track ui build", "build the readiness page"),
    ("provenance check", "is provenance a hit"),
    ("provenance write", "write a provenance manifest"),
    ("license-scan", "license scan one component"),
    ("secret-scan", "scan for secrets"),
    ("review-packet build", "build a review packet"),
    ("decision-drift", "decisions out of step with specs"),
    ("decision-impact", "what a decision touches"),
    ("docs-site build", "render the docs site"),
    ("corpus-graph build", "build the corpus graph"),
    ("assist", "review a spec change"),
    ("init", "set up a new project"),
]


@pytest.mark.parametrize("argv", [[], ["--help"], ["-h"], ["help"]])
def test_help_variants_print_version_and_full_verb_table(tmp_path, argv):
    collected = []
    code = hotdocs_cli.main(list(argv), output_fn=collected.append, cwd=str(tmp_path))

    assert code == 0

    text = "\n".join(str(line) for line in collected)
    assert "hotdocs 0.1.0" in text

    for verb_words, summary in VERB_TABLE:
        assert verb_words in text
        assert summary in text


def test_version_flag_prints_version_and_returns_zero(tmp_path):
    collected = []
    code = hotdocs_cli.main(["--version"], output_fn=collected.append, cwd=str(tmp_path))

    assert code == 0
    text = "\n".join(str(line) for line in collected)
    assert "hotdocs 0.1.0" in text


def test_unknown_verb_returns_two_and_reports_verb_list_on_stderr(tmp_path, capsys):
    code = hotdocs_cli.main(["frobnicate"], cwd=str(tmp_path))

    assert code == 2
    err = capsys.readouterr().err
    assert "unknown verb: frobnicate" in err

    for verb_words, _summary in VERB_TABLE:
        assert verb_words in err


def test_lint_without_component_file_names_path_and_init(tmp_path, capsys):
    code = hotdocs_cli.main(["lint"], cwd=str(tmp_path))

    assert code == 2
    err = capsys.readouterr().err
    assert "gen/spec-linter/spec_linter.py" in err
    assert "hotdocs init" in err


def test_lint_whose_fake_has_no_main_returns_two(tmp_path, capsys):
    component_dir = tmp_path / "gen" / "spec-linter"
    component_dir.mkdir(parents=True)
    (component_dir / "spec_linter.py").write_text("VALUE = 1\n")

    code = hotdocs_cli.main(["lint"], cwd=str(tmp_path))

    assert code == 2
    capsys.readouterr()