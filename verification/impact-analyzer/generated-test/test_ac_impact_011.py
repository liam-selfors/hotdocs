# hotdocs-criterion: sha256:a1311ff7ee945d0e3ed43c8c05b53fb1a247e59d776b7b61b3946fa2bc8cb1ad
import importlib.util
import subprocess
import sys
from pathlib import Path

import impact_analyzer


GIT_PREFIX = [
    "git",
    "-c", "user.name=hotdocs-test",
    "-c", "user.email=test@example.com",
    "-c", "commit.gpgsign=false",
]


def git(repo, *args):
    subprocess.run(GIT_PREFIX + list(args), cwd=str(repo), check=True,
                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_component(repo, slug):
    upper = slug.upper()
    title = slug.title()
    base = repo / "specs" / "components" / slug
    sections = [
        "Purpose", "Scope", "Definitions", "Behavior", "Interfaces",
        "Acceptance criteria", "Open questions", "Change log",
    ]
    lines = [
        "---",
        "id: comp-" + slug,
        "title: " + title,
        "status: draft",
        "owners: [test-team]",
        "sealed: true",
        "source_path: legacy/" + slug + "/",
        "---",
        "",
        "# " + title,
        "",
    ]
    for section in sections:
        lines.append("## " + section)
        lines.append("")
        lines.append("Text for " + section.lower() + ".")
        lines.append("")
    write(base / "component.md", "\n".join(lines))
    write(
        base / "requirements" / ("R-" + upper + "-001.md"),
        "# R-" + upper + "-001\n\nThe component MUST return its input unchanged.\n",
    )
    write(
        base / "acceptance" / ("AC-" + upper + "-001.md"),
        "# AC-" + upper + "-001\n\n"
        + "Covers: R-" + upper + "-001\n"
        + "Kind: generated-test\n\n"
        + "```gherkin\nGiven 1\nWhen it runs\nThen it returns 1\n```\n",
    )
    write(
        base / "constraints.md",
        "# Constraints\n\n- The component MUST finish within 1 second.\n",
    )
    write(
        base / "interface" / "library.md",
        "# Library\n\n```\nrun(x: int) -> int\n```\n",
    )


def load_spec_linter():
    gen = next(p for p in Path(impact_analyzer.__file__).resolve().parents if p.name == "gen")
    base = gen / "spec-linter"
    path = base / "spec_linter.py" if (base / "spec_linter.py").is_file() else base / "spec_linter" / "__init__.py"
    spec = importlib.util.spec_from_file_location("spec_linter", path)
    spec_linter = importlib.util.module_from_spec(spec)
    sys.modules["spec_linter"] = spec_linter
    spec.loader.exec_module(spec_linter)
    return spec_linter


def build_repo(tmp_path):
    repo = tmp_path
    write(repo / "specs" / "glossary.md", "# Glossary\n\n- **Fixture** — a test component.\n")
    write_component(repo, "foo")
    git(repo, "init", "-q", "-b", "main")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "A")
    git(repo, "switch", "-q", "-c", "feature")
    spec_linter = load_spec_linter()
    assert spec_linter.lint(None, repo).hard_failures == 0
    return repo


def test_unknown_changed_id_is_usage_error(tmp_path, capsys, monkeypatch):
    repo = build_repo(tmp_path)
    monkeypatch.chdir(repo)
    capsys.readouterr()

    code = impact_analyzer.main(["--changed", "comp-nope", "--repo-root=" + str(repo)])
    out, err = capsys.readouterr()

    assert code == 2
    assert "comp-nope" in err
    assert out == ""


def test_missing_changed_is_usage_error(tmp_path, capsys, monkeypatch):
    repo = build_repo(tmp_path)
    monkeypatch.chdir(repo)
    capsys.readouterr()

    code = impact_analyzer.main(["--repo-root=" + str(repo)])
    out, err = capsys.readouterr()

    assert code == 2
    assert out == ""


def test_known_changed_id_control_succeeds(tmp_path, capsys, monkeypatch):
    # Control: the same corpus with a known id is not a usage error,
    # so the exit-2 cases above are specific to the bad arguments.
    repo = build_repo(tmp_path)
    monkeypatch.chdir(repo)
    capsys.readouterr()

    code = impact_analyzer.main(["--changed", "comp-foo", "--repo-root=" + str(repo)])
    out, err = capsys.readouterr()

    assert code == 0
    assert "comp-foo\tdirect" in out.splitlines()