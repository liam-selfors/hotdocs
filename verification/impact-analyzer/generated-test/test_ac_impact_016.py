# hotdocs-criterion: sha256:3b6a3e011f6a8ff779d8948927a1ee2944cb9c4e93d917fb4dbcdf8a2758e8e7
import importlib.util
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


def entry_field(value, name):
    if isinstance(value, dict):
        if name == "guarantee_ids":
            return value.get(name)
        return value[name]
    return getattr(value, name)


def git(repo, *args):
    subprocess.run(GIT + list(args), cwd=str(repo), check=True,
                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def component_md(slug, depends_on=None):
    title = slug.title()
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
        "Purpose", "Scope", "Definitions", "Behavior",
        "Interfaces", "Acceptance criteria", "Open questions", "Change log",
    ]:
        lines.append("")
        lines.append("## " + section)
        lines.append("")
        lines.append("Text for " + section.lower() + ".")
    return "\n".join(lines) + "\n"


def requirement_md(slug, sentence="The component MUST return its input unchanged."):
    rid = "R-" + slug.upper() + "-001"
    return "# " + rid + "\n\n" + sentence + "\n"


def acceptance_md(slug):
    up = slug.upper()
    return (
        "# AC-" + up + "-001\n"
        "\n"
        "Covers: R-" + up + "-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given 1\n"
        "When it runs\n"
        "Then it returns 1\n"
        "```\n"
    )


def write_component(repo, slug, depends_on=None):
    base = repo / "specs" / "components" / slug
    up = slug.upper()
    write(base / "component.md", component_md(slug, depends_on))
    write(base / "requirements" / ("R-" + up + "-001.md"), requirement_md(slug))
    write(base / "acceptance" / ("AC-" + up + "-001.md"), acceptance_md(slug))
    write(base / "constraints.md",
          "# Constraints\n\n- The component MUST finish within 1 second.\n")
    write(base / "interface" / "library.md",
          "# Library\n\n```\nrun(x: int) -> int\n```\n")


def load_spec_linter():
    gen = next(p for p in Path(impact_analyzer.__file__).resolve().parents if p.name == "gen")
    base = gen / "spec-linter"
    path = base / "spec_linter.py" if (base / "spec_linter.py").is_file() else base / "spec_linter" / "__init__.py"
    spec = importlib.util.spec_from_file_location("spec_linter", path)
    spec_linter = importlib.util.module_from_spec(spec)
    sys.modules["spec_linter"] = spec_linter
    spec.loader.exec_module(spec_linter)
    return spec_linter


def build_repo(repo):
    write(repo / "specs" / "glossary.md",
          "# Glossary\n\n- **Fixture** — a test component.\n")
    write_component(repo, "foo")
    write_component(repo, "bar", depends_on=["comp-foo"])

    git(repo, "init", "-q", "-b", "main")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "A")
    git(repo, "switch", "-q", "-c", "feature")

    # Changed state: only R-FOO-001.md's text edited.
    write(
        repo / "specs" / "components" / "foo" / "requirements" / "R-FOO-001.md",
        requirement_md("foo", "The component MUST return its input unchanged, always."),
    )


def normalized(report):
    return [
        {
            "component_id": entry_field(e, "component_id"),
            "reason": entry_field(e, "reason"),
            "via": entry_field(e, "via"),
            "guarantee_ids": entry_field(e, "guarantee_ids"),
        }
        for e in field(report, "impacted")
    ]


def test_ac_impact_016(tmp_path):
    repo = tmp_path
    build_repo(repo)

    spec_linter = load_spec_linter()
    assert spec_linter.lint(None, repo).hard_failures == 0

    expected = [{
        "component_id": "comp-foo",
        "reason": "direct",
        "via": None,
        "guarantee_ids": None,
    }]

    first = impact_analyzer.compute_blast_radius(["R-FOO-001"], repo)
    assert field(first, "precondition_error") is None
    assert normalized(first) == expected

    second = impact_analyzer.compute_blast_radius(["AC-FOO-001", "R-FOO-001"], repo)
    assert field(second, "precondition_error") is None
    assert normalized(second) == expected

    third = impact_analyzer.compute_blast_radius(["R-NOPE-001"], repo)
    assert field(third, "precondition_error") is None
    assert list(field(third, "impacted")) == []