import os
import sys
from pathlib import Path

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


class Collector:
    def __init__(self):
        self.lines = []

    def __call__(self, *args, **kwargs):
        sep = kwargs.get("sep", " ")
        if sep is None:
            sep = " "
        self.lines.append(sep.join(str(a) for a in args))

    @property
    def text(self):
        return "\n".join(self.lines)


def _make_dirs(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    tool_root = tmp_path / "fake_tool_root"
    tool_root.mkdir()
    return project, tool_root


def _no_input(*args, **kwargs):
    raise AssertionError("input_fn should not be called")


def _assert_verb_list(text):
    for words, summary in VERB_TABLE:
        assert words in text, f"verb {words!r} missing from output:\n{text}"
        assert summary in text, f"summary {summary!r} missing from output:\n{text}"


@pytest.mark.parametrize("argv", [[], ["--help"], ["-h"], ["help"]])
def test_help_prints_version_and_every_verb(tmp_path, monkeypatch, capsys, argv):
    project, tool_root = _make_dirs(tmp_path)
    monkeypatch.chdir(project)
    out = Collector()
    rc = hotdocs_cli.main(
        list(argv),
        tool_root=tool_root,
        input_fn=_no_input,
        output_fn=out,
        cwd=project,
    )
    captured = capsys.readouterr()
    text = out.text + "\n" + captured.out
    assert rc == 0
    assert "hotdocs 0.1.0" in text
    _assert_verb_list(text)


def test_version_prints_version_and_returns_zero(tmp_path, monkeypatch, capsys):
    project, tool_root = _make_dirs(tmp_path)
    monkeypatch.chdir(project)
    out = Collector()
    rc = hotdocs_cli.main(
        ["--version"],
        tool_root=tool_root,
        input_fn=_no_input,
        output_fn=out,
        cwd=project,
    )
    captured = capsys.readouterr()
    text = out.text + "\n" + captured.out
    assert rc == 0
    assert "hotdocs 0.1.0" in text


def test_unknown_verb_returns_two_and_lists_verbs_on_stderr(tmp_path, monkeypatch, capsys):
    project, tool_root = _make_dirs(tmp_path)
    monkeypatch.chdir(project)
    out = Collector()
    rc = hotdocs_cli.main(
        ["frobnicate"],
        tool_root=tool_root,
        input_fn=_no_input,
        output_fn=out,
        cwd=project,
    )
    captured = capsys.readouterr()
    assert rc == 2
    assert "unknown verb: frobnicate" in captured.err
    _assert_verb_list(captured.err)


def test_lint_missing_everywhere_returns_two_and_names_path(tmp_path, monkeypatch, capsys):
    project, tool_root = _make_dirs(tmp_path)
    monkeypatch.chdir(project)
    assert not (project / "gen" / "spec-linter").exists()
    assert not (tool_root / "gen" / "spec-linter").exists()
    out = Collector()
    rc = hotdocs_cli.main(
        ["lint"],
        tool_root=tool_root,
        input_fn=_no_input,
        output_fn=out,
        cwd=project,
    )
    captured = capsys.readouterr()
    text = "\n".join([out.text, captured.out, captured.err]).replace("\\", "/")
    assert rc == 2
    assert "gen/spec-linter/spec_linter.py" in text


def test_lint_module_without_main_returns_two(tmp_path, monkeypatch, capsys):
    project, tool_root = _make_dirs(tmp_path)
    fake_dir = project / "gen" / "spec-linter"
    fake_dir.mkdir(parents=True)
    (fake_dir / "spec_linter.py").write_text(
        "# fake spec_linter without a main\nVALUE = 1\n", encoding="utf-8"
    )
    monkeypatch.chdir(project)
    out = Collector()
    rc = hotdocs_cli.main(
        ["lint"],
        tool_root=tool_root,
        input_fn=_no_input,
        output_fn=out,
        cwd=project,
    )
    capsys.readouterr()
    assert rc == 2