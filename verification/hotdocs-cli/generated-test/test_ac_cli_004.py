import os
import sys

import pytest

import hotdocs_cli


VERSION_LINE = "hotdocs 0.1.0"

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
        self.chunks = []

    def __call__(self, *args, **kwargs):
        sep = kwargs.get("sep", " ")
        end = kwargs.get("end", "\n")
        self.chunks.append(sep.join(str(a) for a in args) + end)

    @property
    def text(self):
        return "".join(self.chunks)


def _make_project(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "specs").mkdir()
    return project


def _clean_env():
    env = dict(os.environ)
    env.pop("VAR_HOTDOCS_CONFIG", None)
    return env


def _assert_verb_list(text):
    lines = text.splitlines()
    for verb, summary in VERB_TABLE:
        assert verb in text, f"verb {verb!r} missing from:\n{text}"
        assert summary in text, f"summary {summary!r} missing from:\n{text}"
        assert any(
            verb in line and summary in line for line in lines
        ), f"verb {verb!r} not listed with its summary {summary!r} in:\n{text}"


@pytest.fixture
def project(tmp_path, monkeypatch):
    proj = _make_project(tmp_path)
    monkeypatch.chdir(proj)
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    return proj


@pytest.fixture
def fake_tool_root(tmp_path):
    root = tmp_path / "toolroot"
    root.mkdir()
    return root


@pytest.mark.parametrize("argv", [[], ["--help"], ["-h"], ["help"]])
def test_help_prints_version_and_every_verb(argv, project, capsys):
    out = Collector()
    rc = hotdocs_cli.main(
        list(argv), output_fn=out, env=_clean_env(), cwd=project
    )
    captured = capsys.readouterr()
    text = out.text + captured.out
    assert rc == 0
    assert VERSION_LINE in text
    _assert_verb_list(text)


def test_version_prints_version_and_returns_zero(project, capsys):
    out = Collector()
    rc = hotdocs_cli.main(
        ["--version"], output_fn=out, env=_clean_env(), cwd=project
    )
    captured = capsys.readouterr()
    text = out.text + captured.out
    assert rc == 0
    assert VERSION_LINE in text


def test_unknown_verb_returns_2_and_lists_verbs_on_stderr(project, capsys):
    out = Collector()
    rc = hotdocs_cli.main(
        ["frobnicate"], output_fn=out, env=_clean_env(), cwd=project
    )
    captured = capsys.readouterr()
    assert rc == 2
    assert "unknown verb: frobnicate" in captured.err
    _assert_verb_list(captured.err)


def test_lint_missing_under_both_roots_returns_2_naming_path(
    project, fake_tool_root, capsys
):
    assert not (project / "gen" / "spec-linter").exists()
    assert not (fake_tool_root / "gen" / "spec-linter").exists()
    out = Collector()
    rc = hotdocs_cli.main(
        ["lint"],
        tool_root=fake_tool_root,
        output_fn=out,
        env=_clean_env(),
        cwd=project,
    )
    captured = capsys.readouterr()
    text = out.text + captured.out + captured.err
    assert rc == 2
    assert "gen/spec-linter/spec_linter.py" in text.replace("\\", "/")


def test_lint_fake_without_main_returns_2(project, fake_tool_root, capsys):
    fake_dir = project / "gen" / "spec-linter"
    fake_dir.mkdir(parents=True)
    log_path = project / "calls.log"
    (fake_dir / "spec_linter.py").write_text(
        "import json\n"
        f"LOG_PATH = {str(log_path)!r}\n"
        "def lint(paths=None, repo_root=None):\n"
        "    return {'hard_failures': 0}\n",
        encoding="utf-8",
    )
    out = Collector()
    rc = hotdocs_cli.main(
        ["lint"],
        tool_root=fake_tool_root,
        output_fn=out,
        env=_clean_env(),
        cwd=project,
    )
    capsys.readouterr()
    assert rc == 2
    assert not log_path.exists()