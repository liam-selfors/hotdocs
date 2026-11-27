# hotdocs-criterion: sha256:35e8b6274875d9919d70191cd0aafbbebae09d24425d9d3731b50325d865c91a
"""AC-IMPACT-005: a changed product capability pulls in every component
whose `realizes` lists it, tagged `transitive-capability` via that P-id."""

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
                   capture_output=True)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def write_component(repo, slug, extra_frontmatter_lines):
    upper = slug.upper()
    title = slug.title()
    root = repo / "specs" / "components" / slug
    fm = [
        "---",
        "id: comp-" + slug,
        "title: " + title,
        "status: draft",
        "owners: [test-team]",
    ] + list(extra_frontmatter_lines) + ["---"]
    sections = [
        "Purpose", "Scope", "Definitions", "Behavior", "Interfaces",
        "Acceptance criteria", "Open questions", "Change log",
    ]
    body = ["", "# " + title]
    for s in sections:
        body += ["", "## " + s, "", "Text for " + s.lower() + "."]
    write(root / "component.md", "\n".join(fm + body) + "\n")
    write(
        root / "requirements" / ("R-" + upper + "-001.md"),
        "# R-" + upper + "-001\n\nThe component MUST return its input unchanged.\n",
    )
    write(
        root / "acceptance" / ("AC-" + upper + "-001.md"),
        "# AC-" + upper + "-001\n\n"
        + "Covers: R-" + upper + "-001\n"
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


def capability_text(then_line):
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
        "## Capability\n"
        "\n"
        "A user MUST be able to run the pipeline without editing generated code.\n"
        "\n"
        "## Capability scenarios\n"
        "\n"
        "```gherkin\n"
        "Given a spec change\n"
        "When the pipeline runs\n"
        + then_line + "\n"
        "```\n"
    )


def load_spec_linter():
    gen = next(p for p in Path(impact_analyzer.__file__).resolve().parents
               if p.name == "gen")
    base = gen / "spec-linter"
    path = (base / "spec_linter.py" if (base / "spec_linter.py").is_file()
            else base / "spec_linter" / "__init__.py")
    spec = importlib.util.spec_from_file_location("spec_linter", path)
    spec_linter = importlib.util.module_from_spec(spec)
    sys.modules["spec_linter"] = spec_linter
    spec.loader.exec_module(spec_linter)
    return spec_linter


def test_ac_impact_005_changed_capability_includes_realizing_component(tmp_path, capsys):
    repo = tmp_path

    # Before corpus.
    write(repo / "specs" / "glossary.md",
          "# Glossary\n\n- **Fixture** — a test component.\n")
    write(repo / "specs" / "product" / "P-ZERO-EDIT.md",
          capability_text("Then no generated file is edited by hand"))
    write_component(repo, "foo", ["realizes: [P-ZERO-EDIT]"])

    git(repo, "init", "-q", "-b", "main")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "A")
    git(repo, "switch", "-q", "-c", "feature")

    # Changed state: only P-ZERO-EDIT's capability scenarios change.
    write(repo / "specs" / "product" / "P-ZERO-EDIT.md",
          capability_text("Then every generated file is regenerated from specs"))

    # Precondition: the corpus lints clean.
    spec_linter = load_spec_linter()
    assert spec_linter.lint(None, repo).hard_failures == 0

    capsys.readouterr()
    code = impact_analyzer.main(
        ["--changed", "P-ZERO-EDIT", "--repo-root", str(repo), "--format=json"]
    )
    out = capsys.readouterr().out
    assert code == 0, out

    report = json.loads(out)
    assert field(report, "precondition_error") is None
    impacted = field(report, "impacted")
    foo = [e for e in impacted if field(e, "component_id") == "comp-foo"]
    assert len(foo) == 1, impacted
    assert field(foo[0], "reason") == "transitive-capability"
    assert field(foo[0], "via") == "P-ZERO-EDIT"