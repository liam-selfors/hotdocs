# hotdocs-criterion: sha256:318a7a7534c7a023298e0c6d41980bbf2da50f9e69babeb828a3e4c07669ec60
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


def _run(argv, project, capsys, tool_root=None):
    out = Collector()
    kwargs = dict(output_fn=out, env=dict(os.environ), cwd=str(project))
    if tool_root is not None:
        kwargs["tool_root"] = str(tool_root)
    code = hotdocs_cli.run(argv, **kwargs)
    captured = capsys.readouterr()
    return code, out.text() + "\n" + captured.out, captured.err


def _assert_verb_list(text):
    for words, summary in VERBS:
        assert words in text, "verb missing: " + words
        assert summary in text, "summary missing: " + summary


@pytest.mark.parametrize("argv", [[], ["--help"], ["-h"], ["help"]])
def test_help_prints_version_and_all_verbs(argv, tmp_path, capsys):
    project = tmp_path / "project"
    project.mkdir()
    code, out, err = _run(argv, project, capsys)
    assert code == 0
    assert "hotdocs 0.1.0" in out
    _assert_verb_list(out)


def test_version(tmp_path, capsys):
    project = tmp_path / "project"
    project.mkdir()
    code, out, err = _run(["--version"], project, capsys)
    assert code == 0
    assert "hotdocs 0.1.0" in out


def test_unknown_verb(tmp_path, capsys):
    project = tmp_path / "project"
    project.mkdir()
    code, out, err = _run(["frobnicate"], project, capsys)
    assert code == 2
    assert "unknown verb: frobnicate" in err
    _assert_verb_list(err)


def test_lint_missing_module_everywhere(tmp_path, capsys):
    project = tmp_path / "project"
    project.mkdir()
    tool_root = tmp_path / "toolroot"
    tool_root.mkdir()
    code, out, err = _run(["lint"], project, capsys, tool_root=tool_root)
    assert code == 2
    assert "gen/spec-linter/spec_linter.py" in (out + "\n" + err)


def test_lint_module_without_main(tmp_path, capsys):
    project = tmp_path / "project"
    (project / "gen" / "spec-linter").mkdir(parents=True)
    source = "VALUE = " + repr("no main here") + "\n"
    (project / "gen" / "spec-linter" / "spec_linter.py").write_text(source)
    tool_root = tmp_path / "toolroot"
    tool_root.mkdir()
    code, out, err = _run(["lint"], project, capsys, tool_root=tool_root)
    assert code == 2