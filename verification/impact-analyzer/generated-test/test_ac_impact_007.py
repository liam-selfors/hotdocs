# hotdocs-criterion: sha256:1f4efbb875da4bdf35ffb4b735b1777808ac0a5cfa9c9c97625ec7e3114d115a
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


def write_component(repo, slug, depends_on=None, signature="run(x: int) -> int"):
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
    fm.append("---")
    body = ["", "# " + title]
    for section in ["Purpose", "Scope", "Definitions", "Behavior", "Interfaces",
                    "Acceptance criteria", "Open questions", "Change log"]:
        body.append("")
        body.append("## " + section)
        body.append("")
        body.append("Text for " + section.lower() + ".")
    write(base / "component.md", "\n".join(fm + body) + "\n")
    write(base / "requirements" / ("R-" + upper + "-001.md"),
          "# R-" + upper + "-001\n\nThe component MUST return its input unchanged.\n")
    write(base / "acceptance" / ("AC-" + upper + "-001.md"),
          "# AC-" + upper + "-001\n\n"
          "Covers: R-" + upper + "-001\n"
          "Kind: generated-test\n\n"
          "```gherkin\n"
          "Given 1\n"
          "When it runs\n"
          "Then it returns 1\n"
          "```\n")
    write(base / "constraints.md",
          "# Constraints\n\n- The component MUST finish within 1 second.\n")
    write(base / "interface" / "library.md",
          "# Library\n\n```\n" + signature + "\n```\n")


def write_glossary(repo):
    write(repo / "specs" / "glossary.md",
          "# Glossary\n\n- **Fixture** — a test component.\n")


def build_repo(repo, dangling):
    write_glossary(repo)
    write_component(repo, "foo")
    write_component(repo, "bar", depends_on=["comp-missing"] if dangling else None)
    git(repo, "init", "-q", "-b", "main")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "A")
    git(repo, "switch", "-q", "-c", "feature")
    # Changed state: comp-foo's interface signature changes in the working tree.
    write_component(repo, "foo", signature="run(x: int, y: int) -> int")


def load_spec_linter():
    gen = next(p for p in Path(impact_analyzer.__file__).resolve().parents if p.name == "gen")
    base = gen / "spec-linter"
    path = base / "spec_linter.py" if (base / "spec_linter.py").is_file() else base / "spec_linter" / "__init__.py"
    spec = importlib.util.spec_from_file_location("spec_linter", path)
    spec_linter = importlib.util.module_from_spec(spec)
    sys.modules["spec_linter"] = spec_linter
    spec.loader.exec_module(spec_linter)
    return spec_linter


def test_dangling_reference_fails_closed_cli_json(tmp_path, capsys):
    repo = tmp_path
    build_repo(repo, dangling=True)

    spec_linter = load_spec_linter()
    assert spec_linter.lint(None, repo).hard_failures >= 1

    code = impact_analyzer.main(
        ["--changed", "comp-foo", "--repo-root", str(repo), "--format", "json"])
    out = capsys.readouterr().out
    assert code == 1
    report = json.loads(out)
    assert report["precondition_error"] is not None
    assert report["precondition_error"] != ""
    assert report["impacted"] == []


def test_dangling_reference_fails_closed_cli_text(tmp_path, capsys):
    repo = tmp_path
    build_repo(repo, dangling=True)

    code = impact_analyzer.main(["--changed", "comp-foo", "--repo-root=" + str(repo)])
    out = capsys.readouterr().out
    assert code == 1
    lines = [line for line in out.splitlines() if line.strip()]
    assert len(lines) == 1
    assert lines[0].startswith("precondition error: ")
    assert "comp-foo" not in lines[0].split("\t")[0] or "\t" not in lines[0]


def test_dangling_reference_fails_closed_library(tmp_path):
    repo = tmp_path
    build_repo(repo, dangling=True)

    report = impact_analyzer.compute_blast_radius(["comp-foo"], repo)
    assert field(report, "precondition_error") is not None
    assert list(field(report, "impacted")) == []


def test_control_clean_corpus_computes_blast_radius(tmp_path, capsys):
    repo = tmp_path
    build_repo(repo, dangling=False)

    spec_linter = load_spec_linter()
    assert spec_linter.lint(None, repo).hard_failures == 0

    code = impact_analyzer.main(
        ["--changed", "comp-foo", "--repo-root", str(repo), "--format=json"])
    out = capsys.readouterr().out
    assert code == 0
    report = json.loads(out)
    assert report["precondition_error"] is None
    ids = [entry["component_id"] for entry in report["impacted"]]
    assert "comp-foo" in ids
    foo = [e for e in report["impacted"] if e["component_id"] == "comp-foo"][0]
    assert foo["reason"] == "direct"