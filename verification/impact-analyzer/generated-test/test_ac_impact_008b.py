# hotdocs-criterion: sha256:ee7a55661708ca75244f2fbad249bedfb0ae5c976316208e3f0616e5bd2fd2b6
"""AC-IMPACT-008b: a dependent that explicitly narrows its guarantee
dependency to G-FOO-001 is NOT impacted when only G-FOO-002 changes."""

import importlib.util
import json
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


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def git(repo, *args):
    subprocess.run(GIT_PREFIX + list(args), cwd=str(repo), check=True,
                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def component_md(slug, depends_on=None, depends_on_guarantees=None):
    title = slug.title()
    lines = [
        "---",
        "id: comp-" + slug,
        "title: " + title,
        "status: draft",
        "owners: [test-team]",
        "sealed: true",
        "source_path: legacy/" + slug + "/",
    ]
    if depends_on is not None:
        lines.append("depends_on: [" + ", ".join(depends_on) + "]")
    if depends_on_guarantees is not None:
        lines.append(
            "depends_on_guarantees: [" + ", ".join(depends_on_guarantees) + "]"
        )
    lines.append("---")
    lines.append("")
    lines.append("# " + title)
    for section in [
        "Purpose", "Scope", "Definitions", "Behavior", "Interfaces",
        "Acceptance criteria", "Open questions", "Change log",
    ]:
        lines.append("")
        lines.append("## " + section)
        lines.append("")
        lines.append("Fixture text for " + section.lower() + ".")
    return "\n".join(lines) + "\n"


def write_component(repo, slug, depends_on=None, depends_on_guarantees=None,
                    guarantees=None):
    upper = slug.upper()
    root = repo / "specs" / "components" / slug
    write(root / "component.md",
          component_md(slug, depends_on, depends_on_guarantees))
    write(root / "requirements" / ("R-" + upper + "-001.md"),
          "# R-" + upper + "-001\n\nThe component MUST return its input unchanged.\n")
    write(root / "acceptance" / ("AC-" + upper + "-001.md"),
          "# AC-" + upper + "-001\n\n"
          "Covers: R-" + upper + "-001\n"
          "Kind: generated-test\n\n"
          "```gherkin\n"
          "Given 1\n"
          "When it runs\n"
          "Then it returns 1\n"
          "```\n")
    write(root / "constraints.md",
          "# Constraints\n\n- The component MUST finish within 1 second.\n")
    write(root / "interface" / "library.md",
          "# Library\n\n```\nrun(x: int) -> int\n```\n")
    for gid, sentence in (guarantees or {}).items():
        write_guarantee(repo, slug, gid, sentence)


def write_guarantee(repo, slug, gid, sentence):
    write(repo / "specs" / "components" / slug / "interface" / "guarantees"
          / (gid + ".md"),
          "# " + gid + "\n\nThe component MUST " + sentence + ".\n")


def load_spec_linter():
    gen = next(p for p in Path(impact_analyzer.__file__).resolve().parents
               if p.name == "gen")
    base = gen / "spec-linter"
    path = (base / "spec_linter.py" if (base / "spec_linter.py").is_file()
            else base / "spec_linter" / "__init__.py")
    spec = importlib.util.spec_from_file_location("spec_linter", path)
    spec_linter = importlib.util.module_from_spec(spec)
    sys.modules["spec_linter"] = spec_linter
    spec.loader.exec_module(spec_linter)
    return spec_linter


def build_repo(repo):
    # 1. "before" corpus
    write(repo / "specs" / "glossary.md",
          "# Glossary\n\n- **Fixture** — a test component.\n")
    write_component(
        repo, "foo",
        guarantees={
            "G-FOO-001": "return a non-negative value",
            "G-FOO-002": "log every call",
        },
    )
    write_component(
        repo, "bar",
        depends_on=["comp-foo"],
        depends_on_guarantees=["G-FOO-001"],
    )
    # 2. commit A on main
    git(repo, "init", "-q", "-b", "main")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "A")
    # 3. feature branch
    git(repo, "switch", "-q", "-c", "feature")
    # 4. change only G-FOO-002 in the working tree
    write_guarantee(repo, "foo", "G-FOO-002", "log every call with a timestamp")


def test_ac_impact_008b_narrowed_dependent_not_impacted(tmp_path, capsys):
    repo = tmp_path
    build_repo(repo)

    spec_linter = load_spec_linter()
    assert spec_linter.lint(None, repo).hard_failures == 0

    # Public CLI
    code = impact_analyzer.main(
        ["--changed", "comp-foo", "--repo-root", str(repo), "--format=json"]
    )
    out = capsys.readouterr().out
    assert code == 0, out
    report = json.loads(out)
    assert report["precondition_error"] is None
    ids = [e["component_id"] for e in report["impacted"]]
    assert "comp-foo" in ids
    assert "comp-bar" not in ids, report

    # Public library
    lib_report = impact_analyzer.compute_blast_radius(["comp-foo"], repo)
    assert field(lib_report, "precondition_error") is None
    lib_ids = [field(e, "component_id")
               for e in field(lib_report, "impacted")]
    assert "comp-foo" in lib_ids
    assert "comp-bar" not in lib_ids