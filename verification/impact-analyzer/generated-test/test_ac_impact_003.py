# hotdocs-criterion: sha256:dfd1b10c1d5c35c7523f54f5a2a9c4de5631de98edb097e2818a36ab752d948d
import importlib.util
import json
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
    subprocess.run(
        [
            "git",
            "-c", "user.name=hotdocs-test",
            "-c", "user.email=test@example.com",
            "-c", "commit.gpgsign=false",
        ]
        + list(args),
        cwd=str(repo),
        check=True,
        capture_output=True,
    )


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


FENCE = "```"


def library_text(signature):
    return "# Library\n\n" + FENCE + "\n" + signature + "\n" + FENCE + "\n"


def write_component(repo, slug, depends_on=None):
    upper = slug.upper()
    title = slug.title()
    root = repo / "specs" / "components" / slug
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
    write(root / "component.md", "\n".join(lines) + "\n")
    write(
        root / "requirements" / ("R-" + upper + "-001.md"),
        "# R-" + upper + "-001\n\nThe component MUST return its input unchanged.\n",
    )
    write(
        root / "acceptance" / ("AC-" + upper + "-001.md"),
        "# AC-" + upper + "-001\n\n"
        + "Covers: R-" + upper + "-001\n"
        + "Kind: generated-test\n\n"
        + FENCE + "gherkin\n"
        + "Given 1\nWhen it runs\nThen it returns 1\n"
        + FENCE + "\n",
    )
    write(
        root / "constraints.md",
        "# Constraints\n\n- The component MUST finish within 1 second.\n",
    )
    write(root / "interface" / "library.md", library_text("run(x: int) -> int"))


def build_repo(repo):
    write(repo / "specs" / "glossary.md", "# Glossary\n\n- **Fixture** — a test component.\n")
    write_component(repo, "foo")
    write_component(repo, "bar", depends_on=["comp-foo"])
    git(repo, "init", "-q", "-b", "main")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "A")
    git(repo, "switch", "-q", "-c", "feature")
    # Change only comp-foo's interface/library.md (not interface/guarantees/).
    write(
        repo / "specs" / "components" / "foo" / "interface" / "library.md",
        library_text("run(x: int, y: int) -> int"),
    )
    return repo


def find_entry(impacted, component_id):
    matches = [e for e in impacted if field(e, "component_id") == component_id]
    assert len(matches) == 1, impacted
    return matches[0]


def test_library_change_propagates_transitive_interface(tmp_path):
    repo = build_repo(tmp_path)
    spec_linter = load_spec_linter()
    assert spec_linter.lint(None, repo).hard_failures == 0

    report = impact_analyzer.compute_blast_radius(["comp-foo"], repo)
    assert field(report, "precondition_error") is None
    impacted = field(report, "impacted")
    bar = find_entry(impacted, "comp-bar")
    assert field(bar, "reason") == "transitive-interface"
    assert field(bar, "via") == "comp-foo"
    assert field(bar, "guarantee_ids") is None


def test_cli_json_reports_transitive_interface(tmp_path, capsys):
    repo = build_repo(tmp_path)
    spec_linter = load_spec_linter()
    assert spec_linter.lint(None, repo).hard_failures == 0
    capsys.readouterr()

    code = impact_analyzer.main(
        ["--changed", "comp-foo", "--repo-root", str(repo), "--format=json"]
    )
    out = capsys.readouterr().out
    assert code == 0
    data = json.loads(out)
    assert data["precondition_error"] is None
    bar = find_entry(data["impacted"], "comp-bar")
    assert bar["reason"] == "transitive-interface"
    assert bar["via"] == "comp-foo"
    assert "guarantee_ids" not in bar


def test_cli_text_reports_transitive_interface(tmp_path, capsys):
    repo = build_repo(tmp_path)
    spec_linter = load_spec_linter()
    assert spec_linter.lint(None, repo).hard_failures == 0
    capsys.readouterr()

    code = impact_analyzer.main(["--changed", "comp-foo", "--repo-root=" + str(repo)])
    out = capsys.readouterr().out
    assert code == 0
    lines = out.splitlines()
    assert "comp-bar\ttransitive-interface\tvia comp-foo" in lines