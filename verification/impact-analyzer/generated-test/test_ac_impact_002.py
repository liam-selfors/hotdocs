# hotdocs-criterion: sha256:11bc4281dcd56ea6bd2cad628d16f4d2ec6d663943f049b73ee1c9af3adbf6c8
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import impact_analyzer


GIT_PREFIX = [
    "git",
    "-c", "user.name=hotdocs-test",
    "-c", "user.email=test@example.com",
    "-c", "commit.gpgsign=false",
]


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def git(repo, *args):
    subprocess.run(GIT_PREFIX + list(args), cwd=str(repo), check=True,
                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def component_md(slug, depends_on=None, purpose_text="Fixture purpose."):
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
    if depends_on:
        lines.append("depends_on: [" + ", ".join(depends_on) + "]")
    lines.append("---")
    lines.append("")
    lines.append("# " + title)
    sections = [
        ("Purpose", purpose_text),
        ("Scope", "Fixture scope."),
        ("Definitions", "None."),
        ("Behavior", "See `requirements/`."),
        ("Interfaces", "See `interface/`."),
        ("Acceptance criteria", "See `acceptance/`."),
        ("Open questions", "None."),
        ("Change log", "Initial."),
    ]
    for name, text in sections:
        lines.append("")
        lines.append("## " + name)
        lines.append("")
        lines.append(text)
    return "\n".join(lines) + "\n"


def write_component(repo, slug, depends_on=None, purpose_text="Fixture purpose."):
    upper = slug.upper()
    base = repo / "specs" / "components" / slug
    write(base / "component.md", component_md(slug, depends_on, purpose_text))
    write(base / "requirements" / ("R-" + upper + "-001.md"),
          "# R-" + upper + "-001\n\nThe component MUST return its input unchanged.\n")
    write(base / "acceptance" / ("AC-" + upper + "-001.md"),
          "# AC-" + upper + "-001\n\n"
          + "Covers: R-" + upper + "-001\n"
          + "Kind: generated-test\n\n"
          + "```gherkin\nGiven 1\nWhen it runs\nThen it returns 1\n```\n")
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

    foo_interface = repo / "specs" / "components" / "foo" / "interface" / "library.md"
    interface_before = foo_interface.read_bytes()

    # Change comp-foo's component.md narrative only; interface/ untouched.
    write(repo / "specs" / "components" / "foo" / "component.md",
          component_md("foo", purpose_text="Fixture purpose, reworded internally."))

    assert foo_interface.read_bytes() == interface_before
    return repo


def test_internal_component_md_change_does_not_propagate(tmp_path):
    repo = build_repo(tmp_path)

    spec_linter = load_spec_linter()
    assert spec_linter.lint(None, repo).hard_failures == 0

    report = impact_analyzer.compute_blast_radius(["comp-foo"], repo)

    assert field(report, "precondition_error") is None
    impacted = field(report, "impacted")
    ids = [field(e, "component_id") for e in impacted]

    assert "comp-foo" in ids
    foo_entry = impacted[ids.index("comp-foo")]
    assert field(foo_entry, "reason") == "direct"
    assert field(foo_entry, "via") is None
    assert "comp-bar" not in ids
    assert ids == ["comp-foo"]


def test_internal_change_cli_json(tmp_path, capsys):
    repo = build_repo(tmp_path)

    code = impact_analyzer.main(
        ["--changed", "comp-foo", "--repo-root", str(repo), "--format=json"]
    )
    captured = capsys.readouterr()
    assert code == 0
    data = json.loads(captured.out)
    assert data["precondition_error"] is None
    ids = [e["component_id"] for e in data["impacted"]]
    assert "comp-foo" in ids
    foo_entry = data["impacted"][ids.index("comp-foo")]
    assert foo_entry["reason"] == "direct"
    assert foo_entry["via"] is None
    assert "comp-bar" not in ids


def test_internal_change_cli_text(tmp_path, capsys):
    repo = build_repo(tmp_path)

    code = impact_analyzer.main(
        ["--changed=comp-foo", "--repo-root=" + str(repo)]
    )
    captured = capsys.readouterr()
    assert code == 0
    lines = [l for l in captured.out.splitlines() if l.strip()]
    assert lines == ["comp-foo\tdirect"]
    assert "comp-bar" not in captured.out