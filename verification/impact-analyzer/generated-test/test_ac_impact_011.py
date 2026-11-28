# hotdocs-criterion: sha256:e17b229802a61b95f08189f675045bc71d29d9a5a782529967e45a3ff7423856
import importlib.util
import subprocess
import sys
from pathlib import Path

import impact_analyzer


GIT = [
    "git",
    "-c", "user.name=hotdocs-test",
    "-c", "user.email=test@example.com",
    "-c", "commit.gpgsign=false",
]


def git(repo, *args):
    subprocess.run(GIT + list(args), cwd=str(repo), check=True,
                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_component(repo, slug):
    upper = slug.upper()
    title = slug.title()
    base = repo / "specs" / "components" / slug
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
    ]
    for section in ["Purpose", "Scope", "Definitions", "Behavior",
                    "Interfaces", "Acceptance criteria", "Open questions",
                    "Change log"]:
        lines.append("")
        lines.append("## " + section)
        lines.append("")
        lines.append("Text for " + section.lower() + ".")
    write(base / "component.md", "\n".join(lines) + "\n")
    rid = "R-" + upper + "-001"
    write(base / "requirements" / (rid + ".md"),
          "# " + rid + "\n\nThe component MUST return its input unchanged.\n")
    aid = "AC-" + upper + "-001"
    write(base / "acceptance" / (aid + ".md"),
          "# " + aid + "\n\n"
          "Covers: " + rid + "\n"
          "Kind: generated-test\n\n"
          "```gherkin\n"
          "Given 1\n"
          "When it runs\n"
          "Then it returns 1\n"
          "```\n")
    write(base / "constraints.md",
          "# Constraints\n\n- The component MUST finish within 1 second.\n")
    write(base / "interface" / "library.md",
          "# Library\n\n```\nrun(x: int) -> int\n```\n")


def build_repo(repo):
    write(repo / "specs" / "glossary.md",
          "# Glossary\n\n- **Fixture** — a test component.\n")
    write_component(repo, "foo")
    git(repo, "init", "-q", "-b", "main")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "A")
    git(repo, "switch", "-q", "-c", "feature")


def assert_lint_clean(repo_root):
    gen = next(p for p in Path(impact_analyzer.__file__).resolve().parents
               if p.name == "gen")
    base = gen / "spec-linter"
    path = (base / "spec_linter.py" if (base / "spec_linter.py").is_file()
            else base / "spec_linter" / "__init__.py")
    spec = importlib.util.spec_from_file_location("spec_linter", path)
    spec_linter = importlib.util.module_from_spec(spec)
    sys.modules["spec_linter"] = spec_linter
    spec.loader.exec_module(spec_linter)
    assert spec_linter.lint(None, repo_root).hard_failures == 0


def test_unknown_changed_id_is_usage_error(tmp_path, capsys):
    repo = tmp_path
    build_repo(repo)
    assert_lint_clean(repo)
    capsys.readouterr()

    code = impact_analyzer.main(
        ["--changed", "comp-nope", "--repo-root=" + str(repo)])
    out = capsys.readouterr()

    assert code == 2
    assert "comp-nope" in out.err
    assert out.out == ""


def test_missing_changed_is_usage_error(tmp_path, capsys):
    repo = tmp_path
    build_repo(repo)
    assert_lint_clean(repo)
    capsys.readouterr()

    code = impact_analyzer.main(["--repo-root=" + str(repo)])
    capsys.readouterr()

    assert code == 2