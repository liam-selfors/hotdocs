# hotdocs-criterion: sha256:c9595afef8222586be8d344e9e97386e4b3b5b10027c34e045abcd98aec72e84
import os

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


class Collector:
    def __init__(self):
        self.parts = []

    def __call__(self, *args, **kwargs):
        sep = kwargs.get("sep", " ")
        if sep is None:
            sep = " "
        end = kwargs.get("end", "\n")
        if end is None:
            end = "\n"
        self.parts.append(sep.join(str(a) for a in args) + end)

    @property
    def text(self):
        return "".join(self.parts)


def make_dir(tmp_path, name):
    d = tmp_path / name
    d.mkdir(parents=True, exist_ok=True)
    return d


def invoke(argv, tool_root, project, capsys):
    capsys.readouterr()
    out = Collector()
    code = hotdocs_cli.run(
        argv,
        tool_root=str(tool_root),
        output_fn=out,
        input_fn=lambda *a, **k: "",
        env={},
        cwd=str(project),
    )
    captured = capsys.readouterr()
    return code, out.text + captured.out, captured.err


def assert_verb_list(text):
    lines = text.splitlines()
    for words, summary in VERB_TABLE:
        assert any(words in line and summary in line for line in lines), (
            "verb " + repr(words) + " with summary " + repr(summary)
            + " not found in output:\n" + text
        )


@pytest.fixture
def project(tmp_path):
    return make_dir(tmp_path, "project")


@pytest.fixture
def versioned_tool_root(tmp_path):
    root = make_dir(tmp_path, "toolroot")
    (root / "pyproject.toml").write_text(PYPROJECT)
    return root


@pytest.mark.parametrize("argv", [[], ["--help"], ["-h"], ["help"]])
def test_help_prints_version_and_verb_table(argv, project, versioned_tool_root, capsys):
    code, out, err = invoke(argv, versioned_tool_root, project, capsys)
    assert code == 0
    assert "hotdocs 9.8.7a1" in out
    assert_verb_list(out)
    assert "init" in out


def test_version_prints_tool_version(project, versioned_tool_root, capsys):
    code, out, err = invoke(["--version"], versioned_tool_root, project, capsys)
    assert code == 0
    assert "hotdocs 9.8.7a1" in out


@pytest.mark.parametrize("content", [None, "not toml [", "[tool.x]\n"])
def test_version_unknown_when_unreadable(content, tmp_path, project, capsys):
    root = make_dir(tmp_path, "toolroot_unknown")
    if content is not None:
        (root / "pyproject.toml").write_text(content)
    code, out, err = invoke(["--version"], root, project, capsys)
    assert code == 0
    assert "hotdocs unknown" in out
    assert "9.8.7a1" not in out


def test_unknown_verb(project, versioned_tool_root, capsys):
    code, out, err = invoke(["frobnicate"], versioned_tool_root, project, capsys)
    assert code == 2
    assert "unknown verb: frobnicate" in err
    assert_verb_list(err)


def test_lint_missing_module_under_both_roots(tmp_path, project, capsys):
    tool_root = make_dir(tmp_path, "empty_toolroot")
    code, out, err = invoke(["lint"], tool_root, project, capsys)
    assert code == 2
    combined = out + err
    assert "gen/spec-linter/spec_linter.py" in combined.replace(os.sep, "/")


def test_lint_module_without_main(tmp_path, project, capsys):
    tool_root = make_dir(tmp_path, "empty_toolroot2")
    fake_dir = project / "gen" / "spec-linter"
    fake_dir.mkdir(parents=True)
    (fake_dir / "spec_linter.py").write_text("X = " + repr(1) + "\n")
    code, out, err = invoke(["lint"], tool_root, project, capsys)
    assert code == 2