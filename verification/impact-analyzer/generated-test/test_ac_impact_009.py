# hotdocs-criterion: sha256:42f9142984b5e65e9b2c112825d3ac0dc6ed544adfdb7be660dfc544ba3f0c9e
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


def git(repo, *args):
    subprocess.run(GIT_PREFIX + list(args), cwd=str(repo), check=True)


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
    if depends_on is not None:
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
        lines.append("Fixture text.")
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
    write_library(repo, slug, "run(x: int) -> int")


def write_library(repo, slug, signature):
    write(
        repo / "specs" / "components" / slug / "interface" / "library.md",
        "# Library\n\n```\n" + signature + "\n```\n",
    )


def load_spec_linter():
    gen = next(p for p in Path(impact_analyzer.__file__).resolve().parents if p.name == "gen")
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


def test_ac_impact_009_graph_computed_from_component_md_only(tmp_path, capsys):
    repo = tmp_path

    # "Before" corpus: comp-foo depends_on comp-bar, declared only in frontmatter.
    write(repo / "specs" / "glossary.md", "# Glossary\n\n- **Fixture** — a test component.\n")
    write_component(repo, "bar")
    write_component(repo, "foo", depends_on=["comp-bar"])

    git(repo, "init", "-q", "-b", "main")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "A")
    git(repo, "switch", "-q", "-c", "feature")

    # Changed state: comp-bar's interface changes.
    write_library(repo, "bar", "run(x: int, y: int) -> int")

    # No precomputed graph artifact exists anywhere in the repo.
    assert list(repo.rglob("corpus-graph.json")) == []
    assert [p for p in repo.rglob("*graph*.json")] == []

    # Precondition: the corpus lints clean.
    spec_linter = load_spec_linter()
    assert spec_linter.lint(None, repo).hard_failures == 0

    capsys.readouterr()
    code = impact_analyzer.main(
        ["--changed", "comp-bar", "--repo-root", str(repo), "--format=json"]
    )
    captured = capsys.readouterr()
    assert code == 0, captured.err

    report = json.loads(captured.out)
    assert field(report, "precondition_error") is None

    impacted = field(report, "impacted")
    by_id = {field(e, "component_id"): e for e in impacted}

    assert "comp-foo" in by_id, impacted
    foo = by_id["comp-foo"]
    assert field(foo, "reason") == "transitive-interface"
    assert field(foo, "via") == "comp-bar"

    assert "comp-bar" in by_id, impacted
    assert field(by_id["comp-bar"], "reason") == "direct"