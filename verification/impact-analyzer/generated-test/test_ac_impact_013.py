# hotdocs-criterion: sha256:3944de57f95e9f12ab7f138fc471b07a646bd96511b5f18a514302a457e9d629
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


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def opt_field(value, name):
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def load_spec_linter():
    gen = next(p for p in Path(impact_analyzer.__file__).resolve().parents if p.name == "gen")
    base = gen / "spec-linter"
    path = base / "spec_linter.py" if (base / "spec_linter.py").is_file() else base / "spec_linter" / "__init__.py"
    spec = importlib.util.spec_from_file_location("spec_linter", path)
    spec_linter = importlib.util.module_from_spec(spec)
    sys.modules["spec_linter"] = spec_linter
    spec.loader.exec_module(spec_linter)
    return spec_linter


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def write_component(repo, slug, depends_on=None, depends_on_guarantees=None, guarantees=()):
    up = slug.upper()
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
    ]
    if depends_on is not None:
        lines.append("depends_on: [" + ", ".join(depends_on) + "]")
    if depends_on_guarantees is not None:
        lines.append("depends_on_guarantees: [" + ", ".join(depends_on_guarantees) + "]")
    lines.append("---")
    lines.append("")
    lines.append("# " + title)
    for section in ["Purpose", "Scope", "Definitions", "Behavior", "Interfaces",
                    "Acceptance criteria", "Open questions", "Change log"]:
        lines.append("")
        lines.append("## " + section)
        lines.append("")
        lines.append("Text for " + section.lower() + ".")
    write(base / "component.md", "\n".join(lines) + "\n")

    rid = "R-" + up + "-001"
    write(base / "requirements" / (rid + ".md"),
          "# " + rid + "\n\nThe component MUST return its input unchanged.\n")
    acid = "AC-" + up + "-001"
    write(base / "acceptance" / (acid + ".md"),
          "# " + acid + "\n\nCovers: " + rid + "\nKind: generated-test\n\n"
          "```gherkin\nGiven 1\nWhen it runs\nThen it returns 1\n```\n")
    write(base / "constraints.md",
          "# Constraints\n\n- The component MUST finish within 1 second.\n")
    write(base / "interface" / "library.md",
          "# Library\n\n```\nrun(x: int) -> int\n```\n")
    for gid in guarantees:
        write_guarantee(base / "interface" / "guarantees" / (gid + ".md"), gid,
                        "return a value")


def write_guarantee(path, gid, sentence):
    write(path, "# " + gid + "\n\nThe component MUST " + sentence + ".\n")


def impacted_tuples(report):
    assert field(report, "precondition_error") is None
    out = []
    for entry in field(report, "impacted"):
        gids = opt_field(entry, "guarantee_ids")
        out.append((
            field(entry, "component_id"),
            field(entry, "reason"),
            field(entry, "via"),
            list(gids) if gids is not None else None,
        ))
    return out


def test_ac_impact_013(tmp_path):
    repo = tmp_path
    write(repo / "specs" / "glossary.md",
          "# Glossary\n\n- **Fixture** — a test component.\n")
    write_component(repo, "foo", guarantees=["G-FOO-001", "G-FOO-002", "G-FOO-003"])
    write_component(repo, "qux", guarantees=["G-QUX-001"])
    write_component(repo, "bar", depends_on=["comp-foo", "comp-qux"],
                    depends_on_guarantees=["G-QUX-001"])

    gdir = repo / "specs" / "components" / "foo" / "interface" / "guarantees"
    write(gdir / "README.md", "# Guarantees\n\nThese are the guarantees.\n")
    write(gdir / "notes.txt", "some notes\n")
    write_guarantee(gdir / "old" / "G-FOO-009.md", "G-FOO-009", "keep an old promise")

    git(repo, "init", "-q", "-b", "main")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "A")
    git(repo, "switch", "-q", "-c", "feature")

    # Feature branch: only non-guarantee files under interface/guarantees/ change.
    write(gdir / "README.md", "# Guarantees\n\nThese are the edited guarantees.\n")
    write(gdir / "notes.txt", "some edited notes\n")
    write_guarantee(gdir / "old" / "G-FOO-009.md", "G-FOO-009", "keep an edited old promise")

    spec_linter = load_spec_linter()
    assert spec_linter.lint(None, repo).hard_failures == 0

    report = impact_analyzer.compute_blast_radius(["comp-foo"], repo)
    assert impacted_tuples(report) == [("comp-foo", "direct", None, None)]

    # Now also edit G-FOO-002 and delete G-FOO-003.
    write_guarantee(gdir / "G-FOO-002.md", "G-FOO-002", "return a different value")
    (gdir / "G-FOO-003.md").unlink()

    assert spec_linter.lint(None, repo).hard_failures == 0

    report = impact_analyzer.compute_blast_radius(["comp-foo"], repo)
    assert impacted_tuples(report) == [
        ("comp-foo", "direct", None, None),
        ("comp-bar", "transitive-guarantee", "comp-foo", ["G-FOO-002", "G-FOO-003"]),
    ]