# hotdocs-criterion: sha256:ebf567d94119b817e2dbba53a5cf4d72b1e9ff1a93750a3fead5a3d1bddd44a9
import impact_analyzer

import importlib.util
import json
import subprocess
import sys
from pathlib import Path


GIT = [
    "git",
    "-c", "user.name=hotdocs-test",
    "-c", "user.email=test@example.com",
    "-c", "commit.gpgsign=false",
]


def git(repo, *args):
    result = subprocess.run(
        GIT + list(args),
        cwd=str(repo),
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def write_component(repo, slug, depends_on=None):
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
    if depends_on:
        lines.append("depends_on: [" + ", ".join(depends_on) + "]")
    lines.append("---")
    lines.append("")
    lines.append("# " + title)
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
        lines.append("")
        lines.append("## " + section)
        lines.append("")
        lines.append("Text for " + section.lower() + ".")
    write(base / "component.md", "\n".join(lines) + "\n")
    write(
        base / "requirements" / ("R-" + upper + "-001.md"),
        "# R-" + upper + "-001\n\nThe component MUST return its input unchanged.\n",
    )
    write(
        base / "acceptance" / ("AC-" + upper + "-001.md"),
        "# AC-" + upper + "-001\n\n"
        + "Covers: R-" + upper + "-001\n"
        + "Kind: generated-test\n\n"
        + "```gherkin\nGiven 1\nWhen it runs\nThen it returns 1\n```\n",
    )
    write(
        base / "constraints.md",
        "# Constraints\n\n- The component MUST finish within 1 second.\n",
    )
    write_library(repo, slug, "run(x: int) -> int")


def write_library(repo, slug, signature):
    write(
        repo / "specs" / "components" / slug / "interface" / "library.md",
        "# Library\n\n```\n" + signature + "\n```\n",
    )


def load_spec_linter():
    gen = next(
        p for p in Path(impact_analyzer.__file__).resolve().parents if p.name == "gen"
    )
    base = gen / "spec-linter"
    path = (
        base / "spec_linter.py"
        if (base / "spec_linter.py").is_file()
        else base / "spec_linter" / "__init__.py"
    )
    spec = importlib.util.spec_from_file_location("spec_linter", path)
    spec_linter = importlib.util.module_from_spec(spec)
    sys.modules["spec_linter"] = spec_linter
    spec.loader.exec_module(spec_linter)
    return spec_linter


LIB_REL = "specs/components/foo/interface/library.md"


def build_repo(repo, revert_in_c=False):
    write(repo / "specs" / "glossary.md", "# Glossary\n\n- **Fixture** — a test component.\n")
    write_component(repo, "foo")
    write_component(repo, "bar", depends_on=["comp-foo"])

    # Commit A on main.
    git(repo, "init", "-q", "-b", "main")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "A")
    git(repo, "switch", "-q", "-c", "feature")

    # Commit B: change comp-foo's interface/library.md.
    write_library(repo, "foo", "run(x: int, y: int) -> int")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "B")

    # Commit C: either touch only a non-spec file, or revert library.md to A.
    if revert_in_c:
        write_library(repo, "foo", "run(x: int) -> int")
    write(repo / "notes" / "c.txt", "commit C\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "C")


def entries_by_id(report):
    impacted = field(report, "impacted")
    result = {}
    for entry in impacted:
        result[field(entry, "component_id")] = entry
    return result


def test_interface_change_detected_against_merge_base_not_head_parent(tmp_path):
    repo = tmp_path
    build_repo(repo)

    # Sanity: library.md is unchanged between B (HEAD~1) and C (HEAD),
    # but differs between A (merge-base) and the working tree.
    lib_at_parent = git(repo, "show", "HEAD~1:" + LIB_REL)
    lib_at_head = git(repo, "show", "HEAD:" + LIB_REL)
    lib_at_a = git(repo, "show", "main:" + LIB_REL)
    assert lib_at_parent == lib_at_head
    assert lib_at_a != (repo / LIB_REL).read_text()
    assert git(repo, "merge-base", "HEAD", "main").strip() == git(
        repo, "rev-parse", "main"
    ).strip()
    assert git(repo, "status", "--porcelain").strip() == ""

    spec_linter = load_spec_linter()
    assert spec_linter.lint(None, repo).hard_failures == 0

    report = impact_analyzer.compute_blast_radius(["comp-foo"], repo)
    assert field(report, "precondition_error") is None
    by_id = entries_by_id(report)

    assert "comp-foo" in by_id
    assert field(by_id["comp-foo"], "reason") == "direct"

    assert "comp-bar" in by_id
    bar = by_id["comp-bar"]
    assert field(bar, "reason") == "transitive-interface"
    assert field(bar, "via") == "comp-foo"


def test_cli_reports_transitive_interface_against_merge_base(tmp_path, capsys):
    repo = tmp_path
    build_repo(repo)

    code = impact_analyzer.main(
        ["--changed", "comp-foo", "--repo-root", str(repo), "--format=json"]
    )
    out = capsys.readouterr().out
    assert code == 0
    data = json.loads(out)
    assert data["precondition_error"] is None
    by_id = {e["component_id"]: e for e in data["impacted"]}
    assert by_id["comp-foo"]["reason"] == "direct"
    assert by_id["comp-bar"]["reason"] == "transitive-interface"
    assert by_id["comp-bar"]["via"] == "comp-foo"


def test_change_reverted_since_merge_base_is_not_an_interface_change(tmp_path):
    # Control: library.md differs between B (HEAD~1) and C (HEAD) but is
    # identical to the merge-base A, so no interface change happened.
    repo = tmp_path
    build_repo(repo, revert_in_c=True)

    assert git(repo, "show", "HEAD~1:" + LIB_REL) != (repo / LIB_REL).read_text()
    assert git(repo, "show", "main:" + LIB_REL) == (repo / LIB_REL).read_text()

    spec_linter = load_spec_linter()
    assert spec_linter.lint(None, repo).hard_failures == 0

    report = impact_analyzer.compute_blast_radius(["comp-foo"], repo)
    assert field(report, "precondition_error") is None
    by_id = entries_by_id(report)
    assert field(by_id["comp-foo"], "reason") == "direct"
    if "comp-bar" in by_id:
        assert field(by_id["comp-bar"], "reason") != "transitive-interface"