# hotdocs-criterion: sha256:3a01cf934d1c38b7bb419079f492ac0212a1d22136495f75436465fb3ca674c3
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


def load_spec_linter():
    gen = next(p for p in Path(impact_analyzer.__file__).resolve().parents if p.name == "gen")
    base = gen / "spec-linter"
    path = base / "spec_linter.py" if (base / "spec_linter.py").is_file() else base / "spec_linter" / "__init__.py"
    spec = importlib.util.spec_from_file_location("spec_linter", path)
    spec_linter = importlib.util.module_from_spec(spec)
    sys.modules["spec_linter"] = spec_linter
    spec.loader.exec_module(spec_linter)
    return spec_linter


def component_md(slug, extra_lines):
    title = slug.title()
    lines = [
        "---",
        "id: comp-" + slug,
        "title: " + title,
        "status: draft",
        "owners: [test-team]",
    ] + extra_lines + [
        "---",
        "",
        "# " + title,
        "",
    ]
    for section in ["Purpose", "Scope", "Definitions", "Behavior", "Interfaces",
                    "Acceptance criteria", "Open questions", "Change log"]:
        lines += ["## " + section, "", "Fixture text for " + section.lower() + ".", ""]
    # Open questions must be empty-ish for draft? draft allows content; keep text.
    return "\n".join(lines)


def write_component(repo, slug, extra_lines):
    upper = slug.upper()
    root = repo / "specs" / "components" / slug
    write(root / "component.md", component_md(slug, extra_lines))
    write(root / "requirements" / ("R-" + upper + "-001.md"),
          "# R-" + upper + "-001\n\nThe component MUST return its input unchanged.\n")
    write(root / "acceptance" / ("AC-" + upper + "-001.md"),
          "# AC-" + upper + "-001\n\n"
          "Covers: R-" + upper + "-001\n"
          "Kind: generated-test\n\n"
          "```gherkin\nGiven 1\nWhen it runs\nThen it returns 1\n```\n")
    write(root / "constraints.md",
          "# Constraints\n\n- The component MUST finish within 1 second.\n")
    write(root / "interface" / "library.md",
          "# Library\n\n```\nrun(x: int) -> int\n```\n")


def product_md(then_line):
    return (
        "---\n"
        "id: P-ZERO-EDIT\n"
        "title: Zero Edit\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "---\n"
        "\n"
        "# Zero Edit\n"
        "\n"
        "## Purpose\n"
        "\n"
        "The system MUST return input unchanged.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: returning input.\n"
        "\n"
        "## Capability scenarios\n"
        "\n"
        "### CS-ZERO-EDIT-001\n"
        "\n"
        "Covers: P-ZERO-EDIT\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given 1\n"
        "When the system runs\n"
        + then_line + "\n"
        "```\n"
    )


def build_repo(repo):
    write(repo / "specs" / "glossary.md",
          "# Glossary\n\n- **Fixture** — a test component.\n")
    write(repo / "specs" / "product" / "zero-edit.md",
          product_md("Then it returns 1"))
    write_component(repo, "foo", ["realizes: [P-ZERO-EDIT]"])
    write_component(repo, "bar", ["sealed: true", "source_path: legacy/bar/"])

    git(repo, "init", "-q", "-b", "main")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "A")
    git(repo, "switch", "-q", "-c", "feature")

    # Change the capability's own scenarios in the working tree.
    write(repo / "specs" / "product" / "zero-edit.md",
          product_md("Then it returns 1 exactly once"))


def find_entry(entries, component_id):
    matches = [e for e in entries if field(e, "component_id") == component_id]
    assert len(matches) == 1, entries
    return matches[0]


def test_changed_capability_includes_realizing_component_library(tmp_path):
    repo = tmp_path
    build_repo(repo)

    spec_linter = load_spec_linter()
    assert spec_linter.lint(None, repo).hard_failures == 0

    report = impact_analyzer.compute_blast_radius(["P-ZERO-EDIT"], repo)
    assert field(report, "precondition_error") is None
    impacted = field(report, "impacted")

    entry = find_entry(impacted, "comp-foo")
    assert field(entry, "reason") == "transitive-capability"
    assert field(entry, "via") == "P-ZERO-EDIT"
    assert field(entry, "guarantee_ids") is None

    ids = [field(e, "component_id") for e in impacted]
    assert "comp-bar" not in ids


def test_changed_capability_includes_realizing_component_cli(tmp_path, capsys):
    repo = tmp_path
    build_repo(repo)

    spec_linter = load_spec_linter()
    assert spec_linter.lint(None, repo).hard_failures == 0
    capsys.readouterr()

    code = impact_analyzer.main(
        ["--changed", "P-ZERO-EDIT", "--repo-root", str(repo), "--format=json"]
    )
    out = capsys.readouterr().out
    assert code == 0
    data = json.loads(out)
    assert data["precondition_error"] is None

    entry = find_entry(data["impacted"], "comp-foo")
    assert entry["reason"] == "transitive-capability"
    assert entry["via"] == "P-ZERO-EDIT"
    assert "guarantee_ids" not in entry
    assert "comp-bar" not in [e["component_id"] for e in data["impacted"]]


def test_changed_capability_text_output(tmp_path, capsys):
    repo = tmp_path
    build_repo(repo)
    capsys.readouterr()

    code = impact_analyzer.main(
        ["--changed", "P-ZERO-EDIT", "--repo-root=" + str(repo)]
    )
    out = capsys.readouterr().out
    assert code == 0
    lines = [l for l in out.splitlines() if l.strip()]
    assert "comp-foo\ttransitive-capability\tvia P-ZERO-EDIT" in lines