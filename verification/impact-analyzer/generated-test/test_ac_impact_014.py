# hotdocs-criterion: sha256:033bed820b60027f52a3448f77c5243abdaef17a050fb296368027ea5824d246
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

FENCE = "```"


def load_module(path, module_name):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def load_spec_linter():
    gen = next(p for p in Path(impact_analyzer.__file__).resolve().parents if p.name == "gen")
    base = gen / "spec-linter"
    if (base / "spec_linter.py").is_file():
        path = base / "spec_linter.py"
    else:
        path = base / "spec_linter" / "__init__.py"
    return load_module(path, "spec_linter")


def git(repo, *args):
    subprocess.run(GIT + list(args), cwd=str(repo), check=True,
                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def component_md(slug, depends_on=None):
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
    if depends_on:
        lines.append("depends_on: [" + ", ".join(depends_on) + "]")
    lines.append("---")
    lines.append("")
    lines.append("# " + title)
    for section in ["Purpose", "Scope", "Definitions", "Behavior", "Interfaces",
                    "Acceptance criteria", "Open questions", "Change log"]:
        lines.append("")
        lines.append("## " + section)
        lines.append("")
        if section == "Open questions":
            lines.append("None at this time.")
        else:
            lines.append("Text for the " + section.lower() + " section.")
    return "\n".join(lines) + "\n"


def library_md(signature):
    return "# Library\n\n" + FENCE + "\n" + signature + "\n" + FENCE + "\n"


def guarantee_md(gid, sentence):
    return "# " + gid + "\n\nThe component MUST " + sentence + ".\n"


def write_component(repo, slug, depends_on=None, guarantees=None):
    up = slug.upper()
    root = repo / "specs" / "components" / slug
    write(root / "component.md", component_md(slug, depends_on))
    rid = "R-" + up + "-001"
    aid = "AC-" + up + "-001"
    write(root / "requirements" / (rid + ".md"),
          "# " + rid + "\n\nThe component MUST return its input unchanged.\n")
    write(root / "acceptance" / (aid + ".md"),
          "# " + aid + "\n\nCovers: " + rid + "\nKind: generated-test\n\n"
          + FENCE + "gherkin\nGiven 1\nWhen it runs\nThen it returns 1\n" + FENCE + "\n")
    write(root / "constraints.md",
          "# Constraints\n\n- The component MUST finish within 1 second.\n")
    write(root / "interface" / "library.md", library_md("run(x: int) -> int"))
    for gid in (guarantees or []):
        write(root / "interface" / "guarantees" / (gid + ".md"),
              guarantee_md(gid, "keep its output stable"))


def build_fixture(repo):
    write(repo / "specs" / "glossary.md",
          "# Glossary\n\n- **Fixture** — a test component.\n")
    write_component(repo, "foo")
    write_component(repo, "qux", guarantees=["G-QUX-001", "G-QUX-002"])
    write_component(repo, "bar", depends_on=["comp-foo", "comp-qux"])
    write_component(repo, "baz", depends_on=["comp-qux"])

    git(repo, "init", "-q", "-b", "main")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "A")
    git(repo, "switch", "-q", "-c", "feature")

    comps = repo / "specs" / "components"
    write(comps / "foo" / "interface" / "library.md", library_md("run(x: str) -> str"))
    write(comps / "qux" / "interface" / "guarantees" / "G-QUX-001.md",
          guarantee_md("G-QUX-001", "return results in sorted order"))
    write(comps / "qux" / "interface" / "guarantees" / "G-QUX-002.md",
          guarantee_md("G-QUX-002", "never write to disk"))


EXPECTED = (
    "comp-foo\tdirect\n"
    "comp-qux\tdirect\n"
    "comp-bar\ttransitive-interface\tvia comp-foo\n"
    "comp-baz\ttransitive-guarantee\tvia comp-qux\tG-QUX-001,G-QUX-002\n"
)


def test_ac_impact_014_text_output_and_arg_forms(tmp_path, capsys):
    repo = tmp_path
    build_fixture(repo)

    spec_linter = load_spec_linter()
    assert spec_linter.lint(None, repo).hard_failures == 0

    capsys.readouterr()
    code = impact_analyzer.main(["--changed", "comp-foo", "comp-qux",
                                 "--repo-root", str(repo)])
    out, err = capsys.readouterr()
    assert code == 0
    assert err == ""
    assert out == EXPECTED

    code = impact_analyzer.main(["--changed=comp-qux", "--changed", "comp-foo",
                                 "--repo-root=" + str(repo), "--format", "text"])
    out, err = capsys.readouterr()
    assert code == 0
    assert err == ""
    assert out == EXPECTED


def test_ac_impact_014_precondition_error_exit_1(tmp_path, capsys):
    repo = tmp_path
    build_fixture(repo)

    spec_linter = load_spec_linter()
    assert spec_linter.lint(None, repo).hard_failures == 0

    write(repo / "specs" / "components" / "baz" / "component.md",
          component_md("baz", depends_on=["comp-qux", "comp-missing"]))

    capsys.readouterr()
    code = impact_analyzer.main(["--changed", "comp-foo", "--repo-root", str(repo)])
    out, err = capsys.readouterr()
    assert code == 1
    lines = out.splitlines()
    assert len(lines) == 1
    assert lines[0].startswith("precondition error: ")
    assert out == lines[0] + "\n"

    code = impact_analyzer.main(["--changed", "comp-foo", "--repo-root", str(repo),
                                 "--format=json"])
    out, err = capsys.readouterr()
    assert code == 1
    data = json.loads(out)
    assert data["impacted"] == []
    assert isinstance(data["precondition_error"], str)
    assert data["precondition_error"] is not None