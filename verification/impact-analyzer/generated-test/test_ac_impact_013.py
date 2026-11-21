# hotdocs-criterion: sha256:6924a3e0260b4920d63b522bcb0e3cab78edb19b304c93b70ddc1c431af5fb8c
import importlib.util
import subprocess
import sys
from pathlib import Path

import impact_analyzer


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def load_spec_linter():
    gen = next(p for p in Path(impact_analyzer.__file__).resolve().parents if p.name == "gen")
    base = gen / "spec-linter"
    path = base / "spec_linter.py" if (base / "spec_linter.py").is_file() else base / "spec_linter" / "__init__.py"
    spec = importlib.util.spec_from_file_location("spec_linter", path)
    spec_linter = importlib.util.module_from_spec(spec)
    sys.modules["spec_linter"] = spec_linter
    spec.loader.exec_module(spec_linter)
    return spec_linter


def git(repo, *args):
    cmd = [
        "git",
        "-c", "user.name=hotdocs-test",
        "-c", "user.email=test@example.com",
        "-c", "commit.gpgsign=false",
    ] + list(args)
    subprocess.run(cmd, cwd=str(repo), check=True, capture_output=True)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def write_component(repo, slug, depends_on=None, depends_on_guarantees=None, guarantees=None):
    upper = slug.upper()
    title = slug.title()
    root = repo / "specs" / "components" / slug
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
    lines = fm + ["", "# " + title]
    for section in [
        "Purpose",
        "Scope",
        "Definitions",
        "Behavior",
        "Interfaces",
        "Acceptance criteria",
        "Open questions",
        "Change log",
    ]:
        lines += ["", "## " + section, "", "Text for " + section.lower() + "."]
    write(root / "component.md", "\n".join(lines) + "\n")

    rid = "R-" + upper + "-001"
    write(
        root / "requirements" / (rid + ".md"),
        "# " + rid + "\n\nThe component MUST return its input unchanged.\n",
    )
    acid = "AC-" + upper + "-001"
    write(
        root / "acceptance" / (acid + ".md"),
        "# " + acid + "\n\n"
        + "Covers: " + rid + "\n"
        + "Kind: generated-test\n\n"
        + "```gherkin\nGiven 1\nWhen it runs\nThen it returns 1\n```\n",
    )
    write(
        root / "constraints.md",
        "# Constraints\n\n- The component MUST finish within 1 second.\n",
    )
    write(
        root / "interface" / "library.md",
        "# Library\n\n```\nrun(x: int) -> int\n```\n",
    )
    for gid in guarantees or []:
        write(
            root / "interface" / "guarantees" / (gid + ".md"),
            "# " + gid + "\n\nThe component MUST keep promise " + gid + ".\n",
        )
    return root


def build_fixture(repo):
    write(repo / "specs" / "glossary.md", "# Glossary\n\n- **Fixture** — a test component.\n")
    foo = write_component(repo, "foo", guarantees=["G-FOO-001", "G-FOO-002", "G-FOO-003"])
    gdir = foo / "interface" / "guarantees"
    write(gdir / "README.md", "# Guarantees\n\nScaffolding only.\n")
    write(gdir / "notes.txt", "some notes\n")
    write(gdir / "old" / "G-FOO-009.md", "# G-FOO-009\n\nThe component MUST keep an old promise.\n")
    write_component(repo, "qux", guarantees=["G-QUX-001"])
    write_component(
        repo,
        "bar",
        depends_on=["comp-foo", "comp-qux"],
        depends_on_guarantees=["G-QUX-001"],
    )

    git(repo, "init", "-q", "-b", "main")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "A")
    git(repo, "switch", "-q", "-c", "feature")
    return gdir


def apply_non_guarantee_changes(gdir):
    write(gdir / "README.md", "# Guarantees\n\nScaffolding only, edited.\n")
    write(gdir / "notes.txt", "some notes, edited\n")
    write(gdir / "old" / "G-FOO-009.md", "# G-FOO-009\n\nThe component MUST keep an edited old promise.\n")


def summarize(report):
    assert field(report, "precondition_error") is None
    out = []
    for entry in field(report, "impacted"):
        gids = field(entry, "guarantee_ids")
        out.append(
            (
                field(entry, "component_id"),
                field(entry, "reason"),
                field(entry, "via"),
                None if gids is None else list(gids),
            )
        )
    return out


def test_non_guarantee_files_trigger_nothing(tmp_path):
    repo = tmp_path
    gdir = build_fixture(repo)
    spec_linter = load_spec_linter()
    assert spec_linter.lint(None, repo).hard_failures == 0

    apply_non_guarantee_changes(gdir)
    assert spec_linter.lint(None, repo).hard_failures == 0

    report = impact_analyzer.compute_blast_radius(["comp-foo"], repo)
    assert summarize(report) == [("comp-foo", "direct", None, None)]


def test_narrowing_for_other_upstream_does_not_narrow_foo(tmp_path):
    repo = tmp_path
    gdir = build_fixture(repo)
    spec_linter = load_spec_linter()
    assert spec_linter.lint(None, repo).hard_failures == 0

    apply_non_guarantee_changes(gdir)
    write(gdir / "G-FOO-002.md", "# G-FOO-002\n\nThe component MUST keep a changed promise G-FOO-002.\n")
    (gdir / "G-FOO-003.md").unlink()
    assert spec_linter.lint(None, repo).hard_failures == 0

    report = impact_analyzer.compute_blast_radius(["comp-foo"], repo)
    assert summarize(report) == [
        ("comp-foo", "direct", None, None),
        ("comp-bar", "transitive-guarantee", "comp-foo", ["G-FOO-002", "G-FOO-003"]),
    ]