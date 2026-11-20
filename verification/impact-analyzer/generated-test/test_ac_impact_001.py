# hotdocs-criterion: sha256:9551165bd97c80527aac4989763ede632af0a76f939ba97c98cafde5ebaf2407
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


def git(repo, *args):
    subprocess.run(GIT + list(args), cwd=str(repo), check=True,
                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def load_spec_linter():
    gen = next(p for p in Path(impact_analyzer.__file__).resolve().parents if p.name == "gen")
    base = gen / "spec-linter"
    path = base / "spec_linter.py" if (base / "spec_linter.py").is_file() else base / "spec_linter" / "__init__.py"
    spec = importlib.util.spec_from_file_location("spec_linter", path)
    spec_linter = importlib.util.module_from_spec(spec)
    sys.modules["spec_linter"] = spec_linter
    spec.loader.exec_module(spec_linter)
    return spec_linter


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def component_md(slug, purpose_text="This component is a test fixture."):
    title = slug.title()
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
        "",
    ]
    sections = [
        ("Purpose", purpose_text),
        ("Scope", "In scope: returning its input."),
        ("Definitions", "None."),
        ("Behavior", "See `requirements/`."),
        ("Interfaces", "See `interface/`."),
        ("Acceptance criteria", "See `acceptance/`."),
        ("Open questions", "None."),
        ("Change log", "Initial version."),
    ]
    for name, text in sections:
        lines.append("## " + name)
        lines.append("")
        lines.append(text)
        lines.append("")
    return "\n".join(lines)


def acceptance_md(slug, given="1", then="1"):
    up = slug.upper()
    return (
        "# AC-" + up + "-001\n"
        "\n"
        "Covers: R-" + up + "-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given " + given + "\n"
        "When it runs\n"
        "Then it returns " + then + "\n"
        "```\n"
    )


def library_md(signature="run(x: int) -> int"):
    return "# Library\n\n```\n" + signature + "\n```\n"


def write_component(repo, slug):
    up = slug.upper()
    root = repo / "specs" / "components" / slug
    write(root / "component.md", component_md(slug))
    write(root / "requirements" / ("R-" + up + "-001.md"),
          "# R-" + up + "-001\n\nThe component MUST return its input unchanged.\n")
    write(root / "acceptance" / ("AC-" + up + "-001.md"), acceptance_md(slug))
    write(root / "constraints.md",
          "# Constraints\n\n- The component MUST finish within 1 second.\n")
    write(root / "interface" / "library.md", library_md())


def change_library(repo):
    write(repo / "specs/components/foo/interface/library.md",
          library_md("run(x: int, y: int) -> int"))


def change_requirement(repo):
    write(repo / "specs/components/foo/requirements/R-FOO-001.md",
          "# R-FOO-001\n\nThe component MUST return its input unchanged, always.\n")


def change_constraints(repo):
    write(repo / "specs/components/foo/constraints.md",
          "# Constraints\n\n- The component MUST finish within 2 seconds.\n")


def change_component_root(repo):
    write(repo / "specs/components/foo/component.md",
          component_md("foo", "This component is an edited test fixture."))


def change_acceptance(repo):
    write(repo / "specs/components/foo/acceptance/AC-FOO-001.md",
          acceptance_md("foo", given="2", then="2"))


CHANGES = {
    "library": change_library,
    "requirement": change_requirement,
    "constraints": change_constraints,
    "component-root": change_component_root,
    "acceptance": change_acceptance,
}


def build_repo(tmp_path, change):
    repo = tmp_path
    write(repo / "specs" / "glossary.md",
          "# Glossary\n\n- **Fixture** — a test component.\n")
    write_component(repo, "foo")
    write_component(repo, "bar")
    git(repo, "init", "-q", "-b", "main")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "A")
    git(repo, "switch", "-q", "-c", "feature")
    change(repo)
    return repo


def assert_direct_foo(impacted):
    foo = [e for e in impacted if field(e, "component_id") == "comp-foo"]
    assert len(foo) == 1, impacted
    assert field(foo[0], "reason") == "direct"
    assert field(foo[0], "via") is None


@pytest.mark.parametrize("which", sorted(CHANGES))
def test_cli_changed_component_is_direct(tmp_path, capsys, which):
    repo = build_repo(tmp_path, CHANGES[which])
    spec_linter = load_spec_linter()
    assert spec_linter.lint(None, repo).hard_failures == 0

    capsys.readouterr()
    code = impact_analyzer.main(
        ["--changed", "comp-foo", "--repo-root", str(repo), "--format=json"]
    )
    out = capsys.readouterr().out
    assert code == 0, out
    report = json.loads(out)
    assert report["precondition_error"] is None
    assert_direct_foo(report["impacted"])
    # direct entries come first
    assert report["impacted"][0]["component_id"] == "comp-foo"
    assert report["impacted"][0]["reason"] == "direct"


@pytest.mark.parametrize("which", sorted(CHANGES))
def test_library_changed_component_is_direct(tmp_path, which):
    repo = build_repo(tmp_path, CHANGES[which])
    spec_linter = load_spec_linter()
    assert spec_linter.lint(None, repo).hard_failures == 0

    report = impact_analyzer.compute_blast_radius(["comp-foo"], repo)
    assert field(report, "precondition_error") is None
    impacted = list(field(report, "impacted"))
    assert_direct_foo(impacted)
    assert field(impacted[0], "component_id") == "comp-foo"


def test_cli_text_output_lists_direct(tmp_path, capsys):
    repo = build_repo(tmp_path, change_library)
    capsys.readouterr()
    code = impact_analyzer.main(["--changed", "comp-foo", "--repo-root", str(repo)])
    out = capsys.readouterr().out
    assert code == 0, out
    lines = out.splitlines()
    assert lines[0] == "comp-foo\tdirect"