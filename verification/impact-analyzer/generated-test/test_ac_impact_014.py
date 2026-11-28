# hotdocs-criterion: sha256:742b9d736b15fbc670dfcd47bac2b5417f8f8198af3f7724215a1fa4da5b847c
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import impact_analyzer


GIT_PREFIX = [
    "git",
    "-c",
    "user.name=hotdocs-test",
    "-c",
    "user.email=test@example.com",
    "-c",
    "commit.gpgsign=false",
]

SECTIONS = [
    "Purpose",
    "Scope",
    "Definitions",
    "Behavior",
    "Interfaces",
    "Acceptance criteria",
    "Open questions",
    "Change log",
]


def git(repo, *args):
    subprocess.run(GIT_PREFIX + list(args), cwd=str(repo), check=True,
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
    text = "\n".join(lines) + "\n\n# " + title + "\n"
    for section in SECTIONS:
        text += "\n## " + section + "\n\nOne line of text.\n"
    return text


def library_md(signature):
    return "# Library\n\n```\n" + signature + "\n```\n"


def guarantee_md(gid, sentence):
    return "# " + gid + "\n\nThe component MUST " + sentence + "\n"


def write_component(repo, slug, depends_on=None, guarantees=None):
    upper = slug.upper()
    root = repo / "specs" / "components" / slug
    write(root / "component.md", component_md(slug, depends_on))
    rid = "R-" + upper + "-001"
    write(root / "requirements" / (rid + ".md"),
          "# " + rid + "\n\nThe component MUST return its input unchanged.\n")
    aid = "AC-" + upper + "-001"
    write(root / "acceptance" / (aid + ".md"),
          "# " + aid + "\n\nCovers: " + rid + "\nKind: generated-test\n\n"
          "```gherkin\nGiven 1\nWhen it runs\nThen it returns 1\n```\n")
    write(root / "constraints.md",
          "# Constraints\n\n- The component MUST finish within 1 second.\n")
    write(root / "interface" / "library.md", library_md("run(x: int) -> int"))
    for gid, sentence in (guarantees or []):
        write(root / "interface" / "guarantees" / (gid + ".md"),
              guarantee_md(gid, sentence))


def load_spec_linter():
    gen = next(p for p in Path(impact_analyzer.__file__).resolve().parents if p.name == "gen")
    base = gen / "spec-linter"
    path = base / "spec_linter.py" if (base / "spec_linter.py").is_file() else base / "spec_linter" / "__init__.py"
    spec = importlib.util.spec_from_file_location("spec_linter", path)
    spec_linter = importlib.util.module_from_spec(spec)
    sys.modules["spec_linter"] = spec_linter
    spec.loader.exec_module(spec_linter)
    return spec_linter


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def build_fixture(repo):
    write(repo / "specs" / "glossary.md",
          "# Glossary\n\n- **Fixture** — a test component.\n")
    write_component(repo, "foo")
    write_component(repo, "qux", guarantees=[
        ("G-QUX-001", "return a non-negative value."),
        ("G-QUX-002", "reject a null input."),
    ])
    write_component(repo, "bar", depends_on=["comp-foo", "comp-qux"])
    write_component(repo, "baz", depends_on=["comp-qux"])

    git(repo, "init", "-q", "-b", "main")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "A")
    git(repo, "switch", "-q", "-c", "feature")

    # Changed state on the feature branch (working tree).
    write(repo / "specs" / "components" / "foo" / "interface" / "library.md",
          library_md("run(x: int, y: int) -> int"))
    qg = repo / "specs" / "components" / "qux" / "interface" / "guarantees"
    write(qg / "G-QUX-001.md", guarantee_md("G-QUX-001", "return an even value."))
    write(qg / "G-QUX-002.md", guarantee_md("G-QUX-002", "reject an empty input."))


EXPECTED = (
    "comp-foo\tdirect\n"
    "comp-qux\tdirect\n"
    "comp-bar\ttransitive-interface\tvia comp-foo\n"
    "comp-baz\ttransitive-guarantee\tvia comp-qux\tG-QUX-001,G-QUX-002\n"
)


def test_ac_impact_014(tmp_path, capsys):
    repo = tmp_path
    build_fixture(repo)

    spec_linter = load_spec_linter()
    assert spec_linter.lint(None, repo).hard_failures == 0
    capsys.readouterr()

    rc = impact_analyzer.main(["--changed", "comp-foo", "comp-qux", "--repo-root", str(repo)])
    out = capsys.readouterr()
    assert rc == 0
    assert out.err == ""
    assert out.out == EXPECTED

    rc = impact_analyzer.main([
        "--changed=comp-qux", "--changed", "comp-foo",
        "--repo-root=" + str(repo), "--format", "text",
    ])
    out = capsys.readouterr()
    assert rc == 0
    assert out.err == ""
    assert out.out == EXPECTED

    # Break lint: comp-baz now depends on a component that does not exist.
    write(repo / "specs" / "components" / "baz" / "component.md",
          component_md("baz", depends_on=["comp-qux", "comp-missing"]))

    rc = impact_analyzer.main(["--changed", "comp-foo", "--repo-root", str(repo)])
    out = capsys.readouterr()
    assert rc == 1
    lines = out.out.splitlines()
    assert len(lines) == 1, out.out
    assert lines[0].startswith("precondition error: ")

    rc = impact_analyzer.main([
        "--changed", "comp-foo", "--repo-root", str(repo), "--format=json",
    ])
    out = capsys.readouterr()
    assert rc == 1
    report = json.loads(out.out)
    assert field(report, "impacted") == []
    err = field(report, "precondition_error")
    assert err is not None
    assert isinstance(err, str)