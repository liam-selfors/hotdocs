# hotdocs-criterion: sha256:9446bd392422bdd4d0173dcdd89474a76ff4b6b6637c15201c471cc916774c50
import importlib.util
import json
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


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def git(repo, *args):
    subprocess.run(GIT + list(args), cwd=str(repo), check=True,
                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def make_component(repo, slug, depends_on=None):
    upper = slug.upper()
    title = slug.title()
    base = repo / "specs" / "components" / slug
    fm = [
        "---",
        "id: comp-" + slug,
        "title: " + title,
        "status: draft",
        "owners: [test-team]",
        "sealed: true",
        "source_path: legacy/" + slug + "/",
    ]
    if depends_on:
        fm.append("depends_on: [" + ", ".join(depends_on) + "]")
    fm.append("---")
    body = ["", "# " + title]
    for section in ["Purpose", "Scope", "Definitions", "Behavior",
                    "Interfaces", "Acceptance criteria", "Open questions",
                    "Change log"]:
        body += ["", "## " + section, "", "Fixture text."]
    write(base / "component.md", "\n".join(fm + body) + "\n")
    write(base / "requirements" / ("R-" + upper + "-001.md"),
          "# R-" + upper + "-001\n\nThe component MUST return its input unchanged.\n")
    write(base / "acceptance" / ("AC-" + upper + "-001.md"),
          "# AC-" + upper + "-001\n\n"
          + "Covers: R-" + upper + "-001\n"
          + "Kind: generated-test\n\n"
          + "```gherkin\nGiven 1\nWhen it runs\nThen it returns 1\n```\n")
    write(base / "constraints.md",
          "# Constraints\n\n- The component MUST finish within 1 second.\n")
    write(base / "interface" / "library.md",
          "# Library\n\n```\nrun(x: int) -> int\n```\n")


def load_spec_linter():
    gen = next(p for p in Path(impact_analyzer.__file__).resolve().parents if p.name == "gen")
    base = gen / "spec-linter"
    path = base / "spec_linter.py" if (base / "spec_linter.py").is_file() else base / "spec_linter" / "__init__.py"
    spec = importlib.util.spec_from_file_location("spec_linter", path)
    spec_linter = importlib.util.module_from_spec(spec)
    sys.modules["spec_linter"] = spec_linter
    spec.loader.exec_module(spec_linter)
    return spec_linter


def test_ac_impact_012_repo_root_defaults_to_git_root_from_subdirectory(tmp_path, capsys, monkeypatch):
    repo = tmp_path
    write(repo / "specs" / "glossary.md",
          "# Glossary\n\n- **Fixture** — a test component.\n")
    make_component(repo, "foo")
    make_component(repo, "bar", depends_on=["comp-foo"])

    git(repo, "init", "-q", "-b", "main")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "A")
    git(repo, "switch", "-q", "-c", "feature")

    spec_linter = load_spec_linter()
    assert spec_linter.lint(None, repo).hard_failures == 0

    monkeypatch.chdir(repo / "specs")
    capsys.readouterr()

    code = impact_analyzer.main(["--changed", "comp-foo", "--format=json"])
    out = capsys.readouterr().out

    assert code == 0
    report = json.loads(out)
    assert report["precondition_error"] is None
    entries = [e for e in report["impacted"] if e["component_id"] == "comp-foo"]
    assert len(entries) == 1
    assert entries[0]["reason"] == "direct"
    assert entries[0]["via"] is None