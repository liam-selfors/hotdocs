# hotdocs-criterion: sha256:7c0e05e104ab68a4277ba208aeff4b4c36a3a868e80432c8a79b2fe889c32431
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
                   capture_output=True)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def write_component(repo, slug, depends_on=None, depends_on_guarantees=None,
                    guarantees=None):
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
    if depends_on is not None:
        fm.append("depends_on: [" + ", ".join(depends_on) + "]")
    if depends_on_guarantees is not None:
        fm.append("depends_on_guarantees: ["
                  + ", ".join(depends_on_guarantees) + "]")
    fm.append("---")
    body = ["", "# " + title]
    for section in ["Purpose", "Scope", "Definitions", "Behavior",
                    "Interfaces", "Acceptance criteria", "Open questions",
                    "Change log"]:
        body += ["", "## " + section, "", "Fixture text for " + section + "."]
    write(base / "component.md", "\n".join(fm + body) + "\n")

    rid = "R-" + upper + "-001"
    write(base / "requirements" / (rid + ".md"),
          "# " + rid + "\n\nThe component MUST return its input unchanged.\n")
    acid = "AC-" + upper + "-001"
    write(base / "acceptance" / (acid + ".md"),
          "# " + acid + "\n\nCovers: " + rid + "\nKind: generated-test\n\n"
          "```gherkin\nGiven 1\nWhen it runs\nThen it returns 1\n```\n")
    write(base / "constraints.md",
          "# Constraints\n\n- The component MUST finish within 1 second.\n")
    write(base / "interface" / "library.md",
          "# Library\n\n```\nrun(x: int) -> int\n```\n")
    for gid, sentence in (guarantees or {}).items():
        write(base / "interface" / "guarantees" / (gid + ".md"),
              "# " + gid + "\n\nThe component MUST " + sentence + ".\n")


def build_repo(repo):
    write(repo / "specs" / "glossary.md",
          "# Glossary\n\n- **Fixture** — a test component.\n")
    write_component(repo, "foo",
                    guarantees={"G-FOO-001": "preserve insertion order"})
    write_component(repo, "bar", depends_on=["comp-foo"])

    git(repo, "init", "-q", "-b", "main")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "A")
    git(repo, "switch", "-q", "-c", "feature")

    # Change only the guarantee file's sentence.
    write(repo / "specs" / "components" / "foo" / "interface" / "guarantees"
          / "G-FOO-001.md",
          "# G-FOO-001\n\nThe component MUST reject duplicate keys.\n")


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


def find_entry(impacted, component_id):
    matches = [e for e in impacted if field(e, "component_id") == component_id]
    assert len(matches) == 1, impacted
    return matches[0]


def test_ac_impact_008_library_coarse_default(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    build_repo(repo)
    assert_lint_clean(repo)

    report = impact_analyzer.compute_blast_radius(["comp-foo"], repo)
    assert field(report, "precondition_error") is None
    impacted = list(field(report, "impacted"))

    foo = find_entry(impacted, "comp-foo")
    assert field(foo, "reason") == "direct"

    bar = find_entry(impacted, "comp-bar")
    assert field(bar, "reason") == "transitive-guarantee"
    assert field(bar, "via") == "comp-foo"
    assert list(field(bar, "guarantee_ids")) == ["G-FOO-001"]


def test_ac_impact_008_cli_json_coarse_default(tmp_path, capsys):
    repo = tmp_path / "repo"
    repo.mkdir()
    build_repo(repo)
    assert_lint_clean(repo)
    capsys.readouterr()

    code = impact_analyzer.main(
        ["--changed", "comp-foo", "--repo-root", str(repo), "--format=json"])
    out = capsys.readouterr().out
    assert code == 0
    data = json.loads(out)
    assert data["precondition_error"] is None
    bar = find_entry(data["impacted"], "comp-bar")
    assert bar["reason"] == "transitive-guarantee"
    assert bar["via"] == "comp-foo"
    assert bar["guarantee_ids"] == ["G-FOO-001"]


def test_ac_impact_008_cli_text_coarse_default(tmp_path, capsys):
    repo = tmp_path / "repo"
    repo.mkdir()
    build_repo(repo)
    assert_lint_clean(repo)
    capsys.readouterr()

    code = impact_analyzer.main(
        ["--changed", "comp-foo", "--repo-root", str(repo)])
    out = capsys.readouterr().out
    assert code == 0
    lines = out.splitlines()
    assert "comp-bar\ttransitive-guarantee\tvia comp-foo\tG-FOO-001" in lines