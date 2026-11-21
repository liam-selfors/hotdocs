# hotdocs-criterion: sha256:60abd8f8c34702108d0e14456f9d9f10ed89ece44541ae2226951836886b8c67
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


def make_component(repo, slug, depends_on=None, depends_on_guarantees=None,
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
    if depends_on:
        fm.append("depends_on: [" + ", ".join(depends_on) + "]")
    if depends_on_guarantees:
        fm.append("depends_on_guarantees: [" + ", ".join(depends_on_guarantees) + "]")
    fm.append("---")
    body = ["", "# " + title]
    for section in ["Purpose", "Scope", "Definitions", "Behavior",
                    "Interfaces", "Acceptance criteria", "Open questions",
                    "Change log"]:
        body += ["", "## " + section, "", "Fixture text for this section."]
    write(base / "component.md", "\n".join(fm + body) + "\n")
    write(base / "requirements" / ("R-" + upper + "-001.md"),
          "# R-" + upper + "-001\n\nThe component MUST return its input unchanged.\n")
    write(base / "acceptance" / ("AC-" + upper + "-001.md"),
          "# AC-" + upper + "-001\n\nCovers: R-" + upper + "-001\nKind: generated-test\n\n"
          "```gherkin\nGiven 1\nWhen it runs\nThen it returns 1\n```\n")
    write(base / "constraints.md",
          "# Constraints\n\n- The component MUST finish within 1 second.\n")
    write(base / "interface" / "library.md",
          "# Library\n\n```\nrun(x: int) -> int\n```\n")
    for gid, sentence in (guarantees or {}).items():
        write(base / "interface" / "guarantees" / (gid + ".md"),
              "# " + gid + "\n\nThe component MUST " + sentence + ".\n")


def load_spec_linter():
    gen = next(p for p in Path(impact_analyzer.__file__).resolve().parents if p.name == "gen")
    base = gen / "spec-linter"
    path = base / "spec_linter.py" if (base / "spec_linter.py").is_file() else base / "spec_linter" / "__init__.py"
    spec = importlib.util.spec_from_file_location("spec_linter", path)
    spec_linter = importlib.util.module_from_spec(spec)
    sys.modules["spec_linter"] = spec_linter
    spec.loader.exec_module(spec_linter)
    return spec_linter


def build_repo(repo):
    write(repo / "specs" / "glossary.md",
          "# Glossary\n\n- **Fixture** — a test component.\n")
    make_component(repo, "foo", guarantees={
        "G-FOO-001": "return results in input order",
        "G-FOO-002": "never retry a failed call",
    })
    # Narrowed dependent: relies only on G-FOO-001.
    make_component(repo, "bar", depends_on=["comp-foo"],
                   depends_on_guarantees=["G-FOO-001"])
    # Control dependent: no declaration, coarse default applies.
    make_component(repo, "baz", depends_on=["comp-foo"])

    git(repo, "init", "-q", "-b", "main")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "A")
    git(repo, "switch", "-q", "-c", "feature")

    # Change G-FOO-002 only; G-FOO-001 stays byte-identical.
    write(repo / "specs" / "components" / "foo" / "interface" / "guarantees" / "G-FOO-002.md",
          "# G-FOO-002\n\nThe component MUST retry a failed call at most once.\n")


def entries_by_id(impacted):
    return {field(e, "component_id"): e for e in impacted}


def test_narrowed_dependent_excluded_library(tmp_path):
    repo = tmp_path
    build_repo(repo)
    assert load_spec_linter().lint(None, repo).hard_failures == 0

    report = impact_analyzer.compute_blast_radius(["comp-foo"], repo)
    assert field(report, "precondition_error") is None
    impacted = entries_by_id(field(report, "impacted"))

    assert "comp-foo" in impacted
    assert field(impacted["comp-foo"], "reason") == "direct"

    # Control: the guarantee change was detected for the undeclared dependent.
    assert "comp-baz" in impacted
    assert field(impacted["comp-baz"], "reason") == "transitive-guarantee"
    assert field(impacted["comp-baz"], "via") == "comp-foo"
    assert list(field(impacted["comp-baz"], "guarantee_ids")) == ["G-FOO-002"]

    # The criterion: comp-bar only relies on G-FOO-001, which did not change.
    assert "comp-bar" not in impacted


def test_narrowed_dependent_excluded_cli(tmp_path, capsys):
    repo = tmp_path
    build_repo(repo)
    assert load_spec_linter().lint(None, repo).hard_failures == 0

    code = impact_analyzer.main(
        ["--changed", "comp-foo", "--repo-root", str(repo), "--format=json"])
    out = capsys.readouterr().out
    assert code == 0
    data = json.loads(out)
    assert data["precondition_error"] is None
    ids = [e["component_id"] for e in data["impacted"]]
    assert "comp-foo" in ids
    assert "comp-baz" in ids
    assert "comp-bar" not in ids