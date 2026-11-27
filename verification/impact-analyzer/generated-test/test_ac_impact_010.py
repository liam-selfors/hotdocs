# hotdocs-criterion: sha256:262bf5420aca7a21a44c0ac2e519b4905c1639d5d54e1c397e49f4a01788e234
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import impact_analyzer


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

LIB_BEFORE = "run(x: int) -> int"
LIB_AFTER = "run(x: int, y: int) -> int"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def load_module(path, module_name):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def git(repo, *args):
    cmd = [
        "git",
        "-c", "user.name=hotdocs-test",
        "-c", "user.email=test@example.com",
        "-c", "commit.gpgsign=false",
    ] + list(args)
    result = subprocess.run(
        cmd, cwd=str(repo), check=True, capture_output=True, text=True
    )
    return result.stdout


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def library_text(signature):
    return "# Library\n\n```\n" + signature + "\n```\n"


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
    for section in SECTIONS:
        lines.append("")
        lines.append("## " + section)
        lines.append("")
        lines.append("Text for " + section.lower() + ".")
    write(base / "component.md", "\n".join(lines) + "\n")

    req_id = "R-" + upper + "-001"
    write(
        base / "requirements" / (req_id + ".md"),
        "# " + req_id + "\n\nThe component MUST return its input unchanged.\n",
    )
    ac_id = "AC-" + upper + "-001"
    write(
        base / "acceptance" / (ac_id + ".md"),
        "# " + ac_id + "\n\n"
        + "Covers: " + req_id + "\n"
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
    write(base / "interface" / "library.md", library_text(LIB_BEFORE))


def lint_clean(repo_root):
    gen = next(
        p for p in Path(impact_analyzer.__file__).resolve().parents if p.name == "gen"
    )
    base = gen / "spec-linter"
    path = (
        base / "spec_linter.py"
        if (base / "spec_linter.py").is_file()
        else base / "spec_linter" / "__init__.py"
    )
    spec_linter = load_module(path, "spec_linter")
    report = spec_linter.lint(None, repo_root)
    assert report.hard_failures == 0, [
        (f.rule_id, f.file, f.message) for f in report.findings
    ]


def build_repo(repo):
    write(
        repo / "specs" / "glossary.md",
        "# Glossary\n\n- **Fixture** — a test component.\n",
    )
    write_component(repo, "foo")
    write_component(repo, "bar", depends_on=["comp-foo"])

    # Commit A on main.
    git(repo, "init", "-q", "-b", "main")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "A")

    git(repo, "switch", "-q", "-c", "feature")

    # Commit B: change comp-foo's interface/library.md.
    write(
        repo / "specs" / "components" / "foo" / "interface" / "library.md",
        library_text(LIB_AFTER),
    )
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "B")

    # Commit C: an unrelated change; library.md is identical between B and C.
    write(repo / "notes.txt", "unrelated change in commit C\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "C")


def test_ac_impact_010_prior_commit_is_merge_base_not_head_parent(tmp_path, capsys):
    repo = tmp_path
    build_repo(repo)

    lib_rel = "specs/components/foo/interface/library.md"
    current = (repo / lib_rel).read_text()
    # Sanity: library.md unchanged between B (HEAD~1) and C (HEAD/working tree),
    # but changed relative to the merge-base A.
    assert git(repo, "show", "HEAD~1:" + lib_rel) == current
    merge_base = git(repo, "merge-base", "HEAD", "main").strip()
    assert merge_base == git(repo, "rev-parse", "main").strip()
    assert git(repo, "show", merge_base + ":" + lib_rel) != current

    lint_clean(repo)

    rc = impact_analyzer.main(
        ["--changed", "comp-foo", "--repo-root", str(repo), "--format=json"]
    )
    captured = capsys.readouterr()
    assert rc == 0, captured.err

    report = json.loads(captured.out)
    assert field(report, "precondition_error") is None

    impacted = field(report, "impacted")
    by_id = {field(e, "component_id"): e for e in impacted}

    assert "comp-foo" in by_id
    assert field(by_id["comp-foo"], "reason") == "direct"

    assert "comp-bar" in by_id, impacted
    bar = by_id["comp-bar"]
    assert field(bar, "reason") == "transitive-interface"
    assert field(bar, "via") == "comp-foo"