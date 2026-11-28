# hotdocs-criterion: sha256:81ed9f1f6223da8fb4d345107bb635c1f26e67b48a876cf64be39bed0377c6cd
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


class Collector:
    def __init__(self):
        self.lines = []

    def __call__(self, *args, **kwargs):
        sep = kwargs.get("sep", " ")
        self.lines.append(sep.join(str(a) for a in args))

    def text(self):
        return "\n".join(self.lines)


def make_dir(tmp_path, name):
    d = tmp_path / name
    d.mkdir(parents=True, exist_ok=True)
    return d


def write_pyproject(root, content):
    (root / "pyproject.toml").write_text(content, encoding="utf-8")


def good_tool_root(tmp_path):
    root = make_dir(tmp_path, "toolroot")
    content = (
        "[project]\n"
        + "name = " + '"hotdocs"' + "\n"
        + "version = " + '"9.8.7a1"' + "\n"
    )
    write_pyproject(root, content)
    return root


def invoke(argv, tool_root, cwd, capsys):
    out = Collector()
    code = hotdocs_cli.run(
        argv, tool_root=tool_root, output_fn=out, cwd=str(cwd)
    )
    captured = capsys.readouterr()
    stdout = out.text() + "\n" + captured.out
    return code, stdout, captured.err


@pytest.mark.parametrize("argv", [[], ["--help"], ["-h"], ["help"]])
def test_help_prints_version_and_every_verb(tmp_path, capsys, argv):
    tool_root = good_tool_root(tmp_path)
    project = make_dir(tmp_path, "project")
    code, stdout, _err = invoke(list(argv), str(tool_root), project, capsys)
    assert code == 0
    assert "hotdocs 9.8.7a1" in stdout
    for words, summary in VERBS:
        assert words in stdout, words
        assert summary in stdout, summary
    assert "init" in stdout


def test_version_prints_tool_version(tmp_path, capsys):
    tool_root = good_tool_root(tmp_path)
    project = make_dir(tmp_path, "project")
    code, stdout, _err = invoke(["--version"], str(tool_root), project, capsys)
    assert code == 0
    assert "hotdocs 9.8.7a1" in stdout


@pytest.mark.parametrize("variant", ["missing", "invalid", "no_project_table"])
def test_version_unknown(tmp_path, capsys, variant):
    tool_root = make_dir(tmp_path, "toolroot")
    if variant == "invalid":
        write_pyproject(tool_root, "not toml [")
    elif variant == "no_project_table":
        write_pyproject(tool_root, "[tool.x]\n")
    project = make_dir(tmp_path, "project")
    code, stdout, _err = invoke(["--version"], str(tool_root), project, capsys)
    assert code == 0
    assert "hotdocs unknown" in stdout


def test_unknown_verb(tmp_path, capsys):
    tool_root = good_tool_root(tmp_path)
    project = make_dir(tmp_path, "project")
    code, _stdout, err = invoke(["frobnicate"], str(tool_root), project, capsys)
    assert code == 2
    assert "unknown verb: frobnicate" in err
    for words, summary in VERBS:
        assert words in err, words
        assert summary in err, summary


def test_lint_missing_everywhere_names_tool_root_path(tmp_path, capsys):
    tool_root = make_dir(tmp_path, "toolroot")
    project = make_dir(tmp_path, "project")
    code, stdout, err = invoke(["lint"], str(tool_root), project, capsys)
    assert code == 2
    combined = (stdout + "\n" + err).replace("\\", "/")
    assert "gen/spec-linter/spec_linter.py" in combined


def test_lint_module_without_main(tmp_path, capsys):
    tool_root = make_dir(tmp_path, "toolroot")
    project = make_dir(tmp_path, "project")
    linter_dir = project / "gen" / "spec-linter"
    linter_dir.mkdir(parents=True)
    source = (
        "def not_main(argv=None):\n"
        + "    return " + repr(0) + "\n"
    )
    (linter_dir / "spec_linter.py").write_text(source, encoding="utf-8")
    code, _stdout, _err = invoke(["lint"], str(tool_root), project, capsys)
    assert code == 2