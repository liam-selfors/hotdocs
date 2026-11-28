# hotdocs-criterion: sha256:7f81d4d460ea53594d92e0faa4876e2d2ae7c3471d1d1b68dedd46ccd69b9e1e
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import impact_analyzer


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


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


SECTIONS = [
    "## Purpose",
    "## Scope",
    "## Definitions",
    "## Behavior",
    "## Interfaces",
    "## Acceptance criteria",
    "## Open questions",
    "## Change log",
]


def write_component(repo, slug, depends_on=None, guarantees=None):
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
    ]
    if depends_on is not None:
        lines.append("depends_on: [" + ", ".join(depends_on) + "]")
    lines.append("---")
    lines.append("")
    lines.append("# " + title)
    for section in SECTIONS:
        lines.append("")
        lines.append(section)
        lines.append("")
        lines.append("Fixture text for this section.")
    write(base / "component.md", "\n".join(lines) + "\n")

    rid = "R-" + upper + "-001"
    write(
        base / "requirements" / (rid + ".md"),
        "# " + rid + "\n\nThe component MUST return its input unchanged.\n",
    )
    acid = "AC-" + upper + "-001"
    write(
        base / "acceptance" / (acid + ".md"),
        "# " + acid + "\n\n"
        + "Covers: " + rid + "\n"
        + "Kind: generated-test\n\n"
        + "```gherkin\n"
        + "Given 1\n"
        + "When it runs\n"
        + "Then it returns 1\n"
        + "```\n",
    )
    write(
        base / "constraints.md",
        "# Constraints\n\n- The component MUST finish within 1 second.\n",
    )
    write(
        base / "interface" / "library.md",
        "# Library\n\n```\nrun(x: int) -> int\n```\n",
    )
    for gid, sentence in (guarantees or {}).items():
        write_guarantee(repo, slug, gid, sentence)


def write_guarantee(repo, slug, gid, sentence):
    write(
        repo / "specs" / "components" / slug / "interface" / "guarantees" / (gid + ".md"),
        "# " + gid + "\n\nThe component MUST " + sentence + ".\n",
    )


def load_spec_linter():
    gen = next(p for p in Path(impact_analyzer.__file__).resolve().parents if p.name == "gen")
    base = gen / "spec-linter"
    path = base / "spec_linter.py" if (base / "spec_linter.py").is_file() else base / "spec_linter" / "__init__.py"
    spec = importlib.util.spec_from_file_location("spec_linter", path)
    spec_linter = importlib.util.module_from_spec(spec)
    sys.modules["spec_linter"] = spec_linter
    spec.loader.exec_module(spec_linter)
    return spec_linter


def test_ac_impact_008_undeclared_guarantees_coarse_default(tmp_path, capsys):
    repo = tmp_path

    # "Before" corpus.
    write(
        repo / "specs" / "glossary.md",
        "# Glossary\n\n- **Fixture** — a test component.\n",
    )
    write_component(
        repo, "foo",
        guarantees={"G-FOO-001": "keep every stored value readable"},
    )
    write_component(repo, "bar", depends_on=["comp-foo"])

    git(repo, "init", "-q", "-b", "main")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "A")
    git(repo, "switch", "-q", "-c", "feature")

    # Changed state: only comp-foo's guarantee G-FOO-001 changes.
    write_guarantee(repo, "foo", "G-FOO-001", "keep every stored value readable for one hour")

    spec_linter = load_spec_linter()
    assert spec_linter.lint(None, repo).hard_failures == 0

    capsys.readouterr()
    code = impact_analyzer.main(
        ["--changed", "comp-foo", "--repo-root", str(repo), "--format=json"]
    )
    out = capsys.readouterr().out
    assert code == 0, out
    report = json.loads(out)

    assert field(report, "precondition_error") is None
    impacted = field(report, "impacted")
    bar_entries = [e for e in impacted if field(e, "component_id") == "comp-bar"]
    assert len(bar_entries) == 1, impacted
    bar = bar_entries[0]
    assert field(bar, "reason") == "transitive-guarantee"
    assert field(bar, "via") == "comp-foo"
    assert field(bar, "guarantee_ids") == ["G-FOO-001"]