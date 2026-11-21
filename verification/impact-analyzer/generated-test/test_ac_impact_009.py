# hotdocs-criterion: sha256:121c91cb283bbd72c2e91e0fabc342af97c2098a50c9d16579ce25c55d007844
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


def git(repo, *args):
    subprocess.run(GIT + list(args), cwd=str(repo), check=True,
                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def write_component(repo, slug, depends_on=None, signature="run(x: int) -> int"):
    upper = slug.upper()
    title = slug.title()
    base = repo / "specs" / "components" / slug
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
    fm.append("---")
    body = ["", "# " + title]
    for section in [
        "Purpose", "Scope", "Definitions", "Behavior", "Interfaces",
        "Acceptance criteria", "Open questions", "Change log",
    ]:
        body.extend(["", "## " + section, "", "Text for " + section.lower() + "."])
    write(base / "component.md", "\n".join(fm + body) + "\n")
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
    write_library(repo, slug, signature)


def write_library(repo, slug, signature):
    write(
        repo / "specs" / "components" / slug / "interface" / "library.md",
        "# Library\n\n```\n" + signature + "\n```\n",
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


def no_precomputed_graph(repo):
    found = [
        p for p in repo.rglob("*")
        if ".git" not in p.relative_to(repo).parts
        and (p.name == "corpus-graph.json" or "corpus-graph" in p.name)
    ]
    return found


def build_repo(repo):
    write(repo / "specs" / "glossary.md", "# Glossary\n\n- **Fixture** — a test component.\n")
    write_component(repo, "bar")
    write_component(repo, "foo", depends_on=["comp-bar"])
    git(repo, "init", "-q", "-b", "main")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "A")
    git(repo, "switch", "-q", "-c", "feature")
    # Change comp-bar's interface in the working tree.
    write_library(repo, "bar", "run(x: int, y: int) -> int")


def check_report(report):
    assert field(report, "precondition_error") is None
    impacted = field(report, "impacted")
    by_id = {field(e, "component_id"): e for e in impacted}
    assert "comp-foo" in by_id, impacted
    foo = by_id["comp-foo"]
    assert field(foo, "reason") == "transitive-interface"
    assert field(foo, "via") == "comp-bar"
    assert "comp-bar" in by_id
    assert field(by_id["comp-bar"], "reason") == "direct"
    ids = [field(e, "component_id") for e in impacted]
    assert ids.count("comp-foo") == 1


def test_ac_impact_009_library_no_precomputed_graph(tmp_path):
    repo = tmp_path
    build_repo(repo)
    assert no_precomputed_graph(repo) == []
    assert not (repo / "verification").exists()

    spec_linter = load_spec_linter()
    assert spec_linter.lint(None, repo).hard_failures == 0

    report = impact_analyzer.compute_blast_radius(["comp-bar"], repo)
    check_report(report)

    # The analyzer must not have needed (or created) a precomputed graph.
    assert no_precomputed_graph(repo) == []


def test_ac_impact_009_cli_no_precomputed_graph(tmp_path, capsys):
    repo = tmp_path
    build_repo(repo)
    assert no_precomputed_graph(repo) == []

    spec_linter = load_spec_linter()
    assert spec_linter.lint(None, repo).hard_failures == 0
    capsys.readouterr()

    code = impact_analyzer.main(
        ["--changed", "comp-bar", "--repo-root", str(repo), "--format=json"]
    )
    out = capsys.readouterr().out
    assert code == 0
    data = json.loads(out)
    check_report(data)
    assert no_precomputed_graph(repo) == []