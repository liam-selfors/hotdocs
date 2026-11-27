# hotdocs-criterion: sha256:407156b0cea547749009d2df2dd73629ca1fefaece829b2f53f2d3d4e5650523
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


def git(repo, *args):
    subprocess.run(GIT_PREFIX + list(args), cwd=str(repo), check=True,
                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def component_md(slug, depends_on=None, purpose_text="This is a fixture component."):
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
    text = "\n".join(lines) + "\n\n# " + title + "\n\n"
    sections = [
        ("Purpose", purpose_text),
        ("Scope", "Fixture scope."),
        ("Definitions", "None."),
        ("Behavior", "Returns its input."),
        ("Interfaces", "See interface."),
        ("Acceptance criteria", "See acceptance."),
        ("Open questions", "None."),
        ("Change log", "Initial."),
    ]
    parts = []
    for name, body in sections:
        parts.append("## " + name + "\n\n" + body + "\n")
    return text + "\n".join(parts)


def write_component(repo, slug, depends_on=None, purpose_text="This is a fixture component."):
    upper = slug.upper()
    root = repo / "specs" / "components" / slug
    write(root / "component.md", component_md(slug, depends_on, purpose_text))
    write(root / "requirements" / ("R-" + upper + "-001.md"),
          "# R-" + upper + "-001\n\nThe component MUST return its input unchanged.\n")
    write(root / "acceptance" / ("AC-" + upper + "-001.md"),
          "# AC-" + upper + "-001\n\n"
          + "Covers: R-" + upper + "-001\n"
          + "Kind: generated-test\n\n"
          + "```gherkin\n"
          + "Given 1\n"
          + "When it runs\n"
          + "Then it returns 1\n"
          + "```\n")
    write(root / "constraints.md",
          "# Constraints\n\n- The component MUST finish within 1 second.\n")
    write(root / "interface" / "library.md",
          "# Library\n\n```\nrun(x: int) -> int\n```\n")


def assert_lint_clean(repo_root):
    gen = next(p for p in Path(impact_analyzer.__file__).resolve().parents if p.name == "gen")
    base = gen / "spec-linter"
    path = base / "spec_linter.py" if (base / "spec_linter.py").is_file() else base / "spec_linter" / "__init__.py"
    spec = importlib.util.spec_from_file_location("spec_linter", path)
    spec_linter = importlib.util.module_from_spec(spec)
    sys.modules["spec_linter"] = spec_linter
    spec.loader.exec_module(spec_linter)
    assert spec_linter.lint(None, repo_root).hard_failures == 0


def build_repo(tmp_path):
    repo = tmp_path
    write(repo / "specs" / "glossary.md",
          "# Glossary\n\n- **Fixture** — a test component.\n")
    write_component(repo, "foo")
    write_component(repo, "bar", depends_on=["comp-foo"])

    git(repo, "init", "-q", "-b", "main")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "A")
    git(repo, "switch", "-q", "-c", "feature")

    foo_iface = repo / "specs" / "components" / "foo" / "interface" / "library.md"
    iface_before = foo_iface.read_bytes()

    # Change only comp-foo's component.md (Purpose), leaving interface/ untouched.
    write(repo / "specs" / "components" / "foo" / "component.md",
          component_md("foo", None, "This fixture component has an edited purpose."))

    assert foo_iface.read_bytes() == iface_before
    return repo


def assert_report(impacted):
    ids = [field(e, "component_id") for e in impacted]
    assert "comp-foo" in ids
    foo = [e for e in impacted if field(e, "component_id") == "comp-foo"]
    assert len(foo) == 1
    assert field(foo[0], "reason") == "direct"
    assert "comp-bar" not in ids


def test_ac_impact_002_internal_change_does_not_propagate_cli(tmp_path, capsys):
    repo = build_repo(tmp_path)
    assert_lint_clean(repo)
    capsys.readouterr()

    code = impact_analyzer.main(
        ["--changed", "comp-foo", "--repo-root", str(repo), "--format=json"]
    )
    out = capsys.readouterr().out
    assert code == 0
    report = json.loads(out)
    assert report["precondition_error"] is None
    assert_report(report["impacted"])


def test_ac_impact_002_internal_change_does_not_propagate_library(tmp_path):
    repo = build_repo(tmp_path)
    assert_lint_clean(repo)

    report = impact_analyzer.compute_blast_radius(["comp-foo"], repo)
    assert field(report, "precondition_error") is None
    assert_report(field(report, "impacted"))