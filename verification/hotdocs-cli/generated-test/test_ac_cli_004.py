# hotdocs-criterion: sha256:f7b0e5582fec46db89fc5b5c1fbf2ea818e6cbbbf96095663e42ce4c19b4f715
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
    ("spec check", "check criteria from their test authors' view"),
    ("decision new", "draft the next decision record"),
    ("decision ratify", "ratify a decision record"),
    ("decision record-commit", "record the commit that landed a decision"),
    ("component new", "lay out a new component"),
    ("kind new", "scaffold a new asset kind"),
    ("capability new", "lay out a new capability"),
    ("init", "set up a new project"),
]

PYPROJECT = '[project]\nname = "hotdocs"\nversion = "9.8.7a1"\n'


def make_dirs(tmp_path):
    project = tmp_path / "project"
    tool_root = tmp_path / "toolroot"
    project.mkdir()
    tool_root.mkdir()
    return project, tool_root


def call(argv, tool_root, project, capsys):
    captured = []

    def output_fn(*args, **kwargs):
        captured.append(" ".join(str(a) for a in args))

    capsys.readouterr()
    code = hotdocs_cli.run(
        argv,
        tool_root=str(tool_root),
        output_fn=output_fn,
        env={},
        cwd=str(project),
    )
    streams = capsys.readouterr()
    out = "\n".join(captured) + "\n" + streams.out
    return code, out, streams.err


def assert_verb_list(text):
    lines = text.splitlines()
    for words, summary in VERBS:
        assert any(words in line and summary in line for line in lines), (
            "verb " + repr(words) + " with summary " + repr(summary)
            + " not found in:\n" + text
        )


@pytest.mark.parametrize("argv", [[], ["--help"], ["-h"], ["help"]])
def test_help_prints_version_and_every_verb(tmp_path, capsys, argv):
    project, tool_root = make_dirs(tmp_path)
    (tool_root / "pyproject.toml").write_text(PYPROJECT)
    code, out, err = call(argv, tool_root, project, capsys)
    assert code == 0
    assert "hotdocs 9.8.7a1" in out
    assert_verb_list(out)


def test_version_prints_tool_version(tmp_path, capsys):
    project, tool_root = make_dirs(tmp_path)
    (tool_root / "pyproject.toml").write_text(PYPROJECT)
    code, out, err = call(["--version"], tool_root, project, capsys)
    assert code == 0
    assert "hotdocs 9.8.7a1" in out


@pytest.mark.parametrize("content", [None, "not toml [", "[tool.x]\nkey = \"v\"\n"])
def test_version_unknown(tmp_path, capsys, content):
    project, tool_root = make_dirs(tmp_path)
    if content is not None:
        (tool_root / "pyproject.toml").write_text(content)
    code, out, err = call(["--version"], tool_root, project, capsys)
    assert code == 0
    assert "hotdocs unknown" in out


def test_unknown_verb(tmp_path, capsys):
    project, tool_root = make_dirs(tmp_path)
    code, out, err = call(["frobnicate"], tool_root, project, capsys)
    assert code == 2
    assert "unknown verb: frobnicate" in err
    assert_verb_list(err)


def test_lint_missing_component_file(tmp_path, capsys):
    project, tool_root = make_dirs(tmp_path)
    code, out, err = call(["lint"], tool_root, project, capsys)
    assert code == 2
    combined = out + "\n" + err
    assert "gen/spec-linter/spec_linter.py" in combined.replace(os.sep, "/")


def test_lint_component_without_main(tmp_path, capsys):
    project, tool_root = make_dirs(tmp_path)
    fake_dir = project / "gen" / "spec-linter"
    fake_dir.mkdir(parents=True)
    (fake_dir / "spec_linter.py").write_text("VALUE = " + repr(1) + "\n")
    code, out, err = call(["lint"], tool_root, project, capsys)
    assert code == 2