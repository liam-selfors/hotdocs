# hotdocs-criterion: sha256:1439f726fc4c25dcfb798f1c424da72404d6fcc09626f6da926fcc272a401590
"""AC-IMPACT-001: a directly-changed component appears in the blast radius
with reason "direct" (R-IMPACT-001), whichever file in its bundle changed."""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

import impact_analyzer


GIT = [
    "git",
    "-c", "user.name=hotdocs-test",
    "-c", "user.email=test@example.com",
    "-c", "commit.gpgsign=false",
]


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def load_module(path, module_name):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def load_spec_linter():
    gen = next(p for p in Path(impact_analyzer.__file__).resolve().parents if p.name == "gen")
    base = gen / "spec-linter"
    path = base / "spec_linter.py" if (base / "spec_linter.py").is_file() else base / "spec_linter" / "__init__.py"
    return load_module(path, "spec_linter")


def git(repo, *args):
    subprocess.run(GIT + list(args), cwd=str(repo), check=True,
                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_glossary(repo):
    write(repo / "specs" / "glossary.md",
          "# Glossary\n\n- **Fixture** — a test component.\n")


def write_component(repo, slug):
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
        "---",
        "",
        "# " + title,
    ]
    for section in ["Purpose", "Scope", "Definitions", "Behavior",
                    "Interfaces", "Acceptance criteria", "Open questions",
                    "Change log"]:
        lines.append("")
        lines.append("## " + section)
        lines.append("")
        lines.append("Fixture " + section.lower() + " text.")
    write(root / "component.md", "\n".join(lines) + "\n")

    write(root / "requirements" / ("R-" + upper + "-001.md"),
          "# R-" + upper + "-001\n\nThe component MUST return its input unchanged.\n")
    write(root / "acceptance" / ("AC-" + upper + "-001.md"),
          "# AC-" + upper + "-001\n\n"
          "Covers: R-" + upper + "-001\n"
          "Kind: generated-test\n\n"
          "```gherkin\n"
          "Given 1\n"
          "When it runs\n"
          "Then it returns 1\n"
          "```\n")
    write(root / "constraints.md",
          "# Constraints\n\n- The component MUST finish within 1 second.\n")
    write(root / "interface" / "library.md",
          "# Library\n\n```\nrun(x: int) -> int\n```\n")


def change_library(repo):
    write(repo / "specs" / "components" / "foo" / "interface" / "library.md",
          "# Library\n\n```\nrun(x: int, y: int) -> int\n```\n")


def change_requirement(repo):
    write(repo / "specs" / "components" / "foo" / "requirements" / "R-FOO-001.md",
          "# R-FOO-001\n\nThe component MUST return its input unchanged, always.\n")


def change_constraints(repo):
    write(repo / "specs" / "components" / "foo" / "constraints.md",
          "# Constraints\n\n- The component MUST finish within 2 seconds.\n")


def build_repo(repo, change):
    write_glossary(repo)
    write_component(repo, "foo")
    git(repo, "init", "-q", "-b", "main")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "A")
    git(repo, "switch", "-q", "-c", "feature")
    change(repo)


@pytest.mark.parametrize(
    "change",
    [change_library, change_requirement, change_constraints],
    ids=["interface-library", "requirement", "constraints"],
)
def test_changed_component_is_direct(tmp_path, capsys, change):
    repo = tmp_path
    build_repo(repo, change)

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
    matches = [e for e in impacted if field(e, "component_id") == "comp-foo"]
    assert len(matches) == 1, impacted
    entry = matches[0]
    assert field(entry, "reason") == "direct"
    assert field(entry, "via") is None