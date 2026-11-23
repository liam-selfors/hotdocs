# hotdocs-criterion: sha256:f5a6f54837b488511465f0f8af6367a17347839370be2bfdf0f478d56119a688
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

PYPROJECT = '[project]\nname = "hotdocs"\nversion = "9.8.7a1"\n'


def _no_input(*args, **kwargs):
    raise AssertionError("input_fn must not be called")


def _call(argv, tool_root, project, capsys):
    lines = []

    def output_fn(*args, **kwargs):
        sep = kwargs.get("sep", " ")
        lines.append(sep.join(str(a) for a in args))

    capsys.readouterr()
    code = hotdocs_cli.run(
        argv,
        tool_root=tool_root,
        input_fn=_no_input,
        output_fn=output_fn,
        env=dict(os.environ),
        cwd=str(project),
    )
    captured = capsys.readouterr()
    out = "\n".join(lines) + "\n" + captured.out
    return code, out, captured.err


@pytest.fixture
def project(tmp_path):
    p = tmp_path / "project"
    p.mkdir()
    return p


@pytest.fixture
def versioned_root(tmp_path):
    root = tmp_path / "toolroot"
    root.mkdir()
    (root / "pyproject.toml").write_text(PYPROJECT, encoding="utf-8")
    return root


def _assert_verb_lines(text):
    text_lines = text.splitlines()
    for words, summary in VERBS:
        assert any(words in line and summary in line for line in text_lines), (
            "verb " + repr(words) + " with summary " + repr(summary) + " not listed in:\n" + text
        )


@pytest.mark.parametrize("argv", [[], ["--help"], ["-h"], ["help"]])
def test_help_prints_version_and_every_verb(argv, project, versioned_root, capsys):
    code, out, err = _call(argv, str(versioned_root), project, capsys)
    assert code == 0
    assert "hotdocs 9.8.7a1" in out
    _assert_verb_lines(out)
    assert any("init" in line and "set up a new project" in line for line in out.splitlines())


def test_version_prints_tool_version(project, versioned_root, capsys):
    code, out, err = _call(["--version"], str(versioned_root), project, capsys)
    assert code == 0
    assert "hotdocs 9.8.7a1" in out


@pytest.mark.parametrize("content", [None, "not toml [", "[tool.x]\n"])
def test_version_unknown_when_unreadable(content, tmp_path, project, capsys):
    root = tmp_path / "toolroot_unknown"
    root.mkdir()
    if content is not None:
        (root / "pyproject.toml").write_text(content, encoding="utf-8")
    code, out, err = _call(["--version"], str(root), project, capsys)
    assert code == 0
    assert "hotdocs unknown" in out
    assert "hotdocs 9.8.7a1" not in out


def test_unknown_verb(tmp_path, project, capsys):
    root = tmp_path / "toolroot_empty"
    root.mkdir()
    code, out, err = _call(["frobnicate"], str(root), project, capsys)
    assert code == 2
    assert "unknown verb: frobnicate" in err
    for words, summary in VERBS:
        assert words in err, "verb " + repr(words) + " missing from stderr:\n" + err


def test_lint_missing_module_names_tool_root_path(tmp_path, project, capsys):
    root = tmp_path / "toolroot_empty"
    root.mkdir()
    code, out, err = _call(["lint"], str(root), project, capsys)
    assert code == 2
    combined = (err + "\n" + out).replace("\\", "/")
    assert "gen/spec-linter/spec_linter.py" in combined


def test_lint_module_without_main(tmp_path, project, capsys):
    root = tmp_path / "toolroot_empty"
    root.mkdir()
    fake_dir = project / "gen" / "spec-linter"
    fake_dir.mkdir(parents=True)
    (fake_dir / "spec_linter.py").write_text("X = " + repr(1) + "\n", encoding="utf-8")
    code, out, err = _call(["lint"], str(root), project, capsys)
    assert code == 2