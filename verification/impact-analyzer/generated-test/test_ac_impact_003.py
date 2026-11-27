# hotdocs-criterion: sha256:2feebfd2389b09d3579a87d9449798132f80ec970b929570dcbf156001ee4bd9
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

LIBRARY_BEFORE = "# Library\n\n```\nrun(x: int) -> int\n```\n"
LIBRARY_AFTER = "# Library\n\n```\nrun(x: int, y: int) -> int\n```\n"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def load_module(path, module_name):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def git(repo, *args):
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=hotdocs-test",
            "-c",
            "user.email=test@example.com",
            "-c",
            "commit.gpgsign=false",
        ]
        + list(args),
        cwd=str(repo),
        check=True,
        capture_output=True,
    )


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


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
        lines.append("Fixture text for " + section.lower() + ".")
    write(base / "component.md", "\n".join(lines) + "\n")

    req_id = "R-" + upper + "-001"
    ac_id = "AC-" + upper + "-001"
    write(
        base / "requirements" / (req_id + ".md"),
        "# " + req_id + "\n\nThe component MUST return its input unchanged.\n",
    )
    write(
        base / "acceptance" / (ac_id + ".md"),
        "# "
        + ac_id
        + "\n\nCovers: "
        + req_id
        + "\nKind: generated-test\n\n```gherkin\nGiven 1\nWhen it runs\nThen it returns 1\n```\n",
    )
    write(
        base / "constraints.md",
        "# Constraints\n\n- The component MUST finish within 1 second.\n",
    )
    write(base / "interface" / "library.md", LIBRARY_BEFORE)


def build_repo(repo):
    write(
        repo / "specs" / "glossary.md",
        "# Glossary\n\n- **Fixture** — a test component.\n",
    )
    write_component(repo, "foo")
    write_component(repo, "bar", depends_on=["comp-foo"])

    git(repo, "init", "-q", "-b", "main")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "A")
    git(repo, "switch", "-q", "-c", "feature")

    # Change only comp-foo's interface/library.md (nothing under guarantees/).
    write(
        repo / "specs" / "components" / "foo" / "interface" / "library.md",
        LIBRARY_AFTER,
    )


def assert_lint_clean(repo_root):
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
    assert spec_linter.lint(None, repo_root).hard_failures == 0


def find_entry(impacted, component_id):
    matches = [e for e in impacted if field(e, "component_id") == component_id]
    assert len(matches) == 1, "expected exactly one entry for " + component_id + ": " + repr(impacted)
    return matches[0]


def test_ac_impact_003_library_change_propagates_cli(tmp_path, capsys):
    repo = tmp_path
    build_repo(repo)
    assert_lint_clean(repo)

    capsys.readouterr()
    code = impact_analyzer.main(
        ["--changed", "comp-foo", "--repo-root", str(repo), "--format=json"]
    )
    out = capsys.readouterr().out
    assert code == 0, out

    report = json.loads(out)
    assert report["precondition_error"] is None
    entry = find_entry(report["impacted"], "comp-bar")
    assert entry["reason"] == "transitive-interface"
    assert entry["via"] == "comp-foo"


def test_ac_impact_003_library_change_propagates_library(tmp_path):
    repo = tmp_path
    build_repo(repo)
    assert_lint_clean(repo)

    report = impact_analyzer.compute_blast_radius(["comp-foo"], repo)
    assert field(report, "precondition_error") is None
    impacted = field(report, "impacted")
    entry = find_entry(impacted, "comp-bar")
    assert field(entry, "reason") == "transitive-interface"
    assert field(entry, "via") == "comp-foo"