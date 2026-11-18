# hotdocs-criterion: sha256:f62814e0a3cf92033b2a7cc59ffe8c82d88fcb98431f80c31267682d165b084f
import os

import pytest

import hotdocs_cli


VERBS = [
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


def _make_dirs(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    tool_root = tmp_path / "toolroot"
    tool_root.mkdir()
    return project, tool_root


def _run(argv, project, tool_root, capsys):
    captured = []

    def out(*args, **kwargs):
        captured.append(" ".join(str(a) for a in args))

    def no_input(*args, **kwargs):
        raise AssertionError("input_fn should not be called")

    rc = hotdocs_cli.main(
        argv,
        tool_root=tool_root,
        input_fn=no_input,
        output_fn=out,
        env=dict(os.environ),
        cwd=project,
    )
    std = capsys.readouterr()
    return rc, "\n".join(captured) + "\n" + std.out, std.err


def _assert_verb_list(text):
    for words, summary in VERBS:
        assert words in text, "verb missing from list: " + repr(words)
        assert summary in text, "summary missing from list: " + repr(summary)


@pytest.mark.parametrize("argv", [[], ["--help"], ["-h"], ["help"]])
def test_help_prints_version_and_every_verb(tmp_path, capsys, argv):
    project, tool_root = _make_dirs(tmp_path)
    rc, out, err = _run(argv, project, tool_root, capsys)
    assert rc == 0
    combined = out + "\n" + err
    assert "hotdocs 0.1.0" in combined
    _assert_verb_list(combined)
    assert "init" in combined


def test_version_prints_version_and_returns_zero(tmp_path, capsys):
    project, tool_root = _make_dirs(tmp_path)
    rc, out, err = _run(["--version"], project, tool_root, capsys)
    assert rc == 0
    assert "hotdocs 0.1.0" in out + "\n" + err


def test_unknown_verb_returns_two_with_verb_list_on_stderr(tmp_path, capsys):
    project, tool_root = _make_dirs(tmp_path)
    rc, out, err = _run(["frobnicate"], project, tool_root, capsys)
    assert rc == 2
    assert "unknown verb: frobnicate" in err
    _assert_verb_list(err)


def test_lint_missing_under_both_roots_returns_two_naming_path(tmp_path, capsys):
    project, tool_root = _make_dirs(tmp_path)
    rc, out, err = _run(["lint"], project, tool_root, capsys)
    assert rc == 2
    combined = (out + "\n" + err).replace("\\", "/")
    assert "gen/spec-linter/spec_linter.py" in combined


def test_lint_module_without_main_returns_two(tmp_path, capsys):
    project, tool_root = _make_dirs(tmp_path)
    fake_dir = project / "gen" / "spec-linter"
    fake_dir.mkdir(parents=True)
    source = "# fake spec-linter with no main\n" + "VALUE = " + repr(1) + "\n"
    (fake_dir / "spec_linter.py").write_text(source)
    rc, out, err = _run(["lint"], project, tool_root, capsys)
    assert rc == 2