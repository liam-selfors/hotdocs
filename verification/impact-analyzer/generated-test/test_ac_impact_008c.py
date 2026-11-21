# hotdocs-criterion: sha256:ad60d9bc4f882dc1ebbb1e59ed5118c1ff5147adf409adb8edcef4c83ac4d2a2
"""AC-IMPACT-008c: narrowing via depends_on_guarantees still includes a
dependent when one of its specifically declared guarantees changed."""

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
                   capture_output=True)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_component(repo, slug, depends_on=None, depends_on_guarantees=None,
                    guarantees=None):
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
    if depends_on_guarantees is not None:
        lines.append("depends_on_guarantees: ["
                     + ", ".join(depends_on_guarantees) + "]")
    lines.append("---")
    lines.append("")
    lines.append("# " + title)
    for section in ["Purpose", "Scope", "Definitions", "Behavior",
                    "Interfaces", "Acceptance criteria", "Open questions",
                    "Change log"]:
        lines.append("")
        lines.append("## " + section)
        lines.append("")
        if section == "Open questions":
            lines.append("None.")
        else:
            lines.append("Fixture " + section.lower() + " text.")
    write(base / "component.md", "\n".join(lines) + "\n")

    rid = "R-" + upper + "-001"
    write(base / "requirements" / (rid + ".md"),
          "# " + rid + "\n\nThe component MUST return its input unchanged.\n")
    acid = "AC-" + upper + "-001"
    write(base / "acceptance" / (acid + ".md"),
          "# " + acid + "\n\n"
          + "Covers: " + rid + "\n"
          + "Kind: generated-test\n\n"
          + "```gherkin\n"
          + "Given 1\n"
          + "When it runs\n"
          + "Then it returns 1\n"
          + "```\n")
    write(base / "constraints.md",
          "# Constraints\n\n- The component MUST finish within 1 second.\n")
    write(base / "interface" / "library.md",
          "# Library\n\n```\nrun(x: int) -> int\n```\n")
    for gid, sentence in (guarantees or {}).items():
        write_guarantee(repo, slug, gid, sentence)


def write_guarantee(repo, slug, gid, sentence):
    write(repo / "specs" / "components" / slug / "interface" / "guarantees"
          / (gid + ".md"),
          "# " + gid + "\n\nThe component MUST " + sentence + ".\n")


def build_repo(repo):
    write(repo / "specs" / "glossary.md",
          "# Glossary\n\n- **Fixture** — a test component.\n")
    write_component(
        repo, "foo",
        guarantees={
            "G-FOO-001": "return results in sorted order",
            "G-FOO-002": "never raise on empty input",
        },
    )
    write_component(
        repo, "bar",
        depends_on=["comp-foo"],
        depends_on_guarantees=["G-FOO-001"],
    )
    git(repo, "init", "-q", "-b", "main")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "A")
    git(repo, "switch", "-q", "-c", "feature")
    # This commit changes G-FOO-001 only.
    write_guarantee(repo, "foo", "G-FOO-001",
                    "return results in reverse sorted order")


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


def find_entry(impacted, component_id):
    matches = [e for e in impacted if field(e, "component_id") == component_id]
    assert len(matches) == 1, (component_id, impacted)
    return matches[0]


def test_fixture_lints_clean(tmp_path):
    build_repo(tmp_path)
    spec_linter = load_spec_linter()
    assert spec_linter.lint(None, tmp_path).hard_failures == 0


def test_library_includes_bar_for_declared_changed_guarantee(tmp_path):
    build_repo(tmp_path)
    report = impact_analyzer.compute_blast_radius(["comp-foo"], tmp_path)
    assert field(report, "precondition_error") is None
    impacted = field(report, "impacted")

    foo = find_entry(impacted, "comp-foo")
    assert field(foo, "reason") == "direct"

    bar = find_entry(impacted, "comp-bar")
    assert field(bar, "reason") == "transitive-guarantee"
    assert field(bar, "via") == "comp-foo"
    assert list(field(bar, "guarantee_ids")) == ["G-FOO-001"]


def test_cli_json_includes_bar_for_declared_changed_guarantee(tmp_path, capsys):
    build_repo(tmp_path)
    code = impact_analyzer.main(
        ["--changed", "comp-foo", "--repo-root", str(tmp_path),
         "--format=json"])
    out = capsys.readouterr().out
    assert code == 0
    data = json.loads(out)
    assert data["precondition_error"] is None
    impacted = data["impacted"]
    ids = [e["component_id"] for e in impacted]
    assert ids == ["comp-foo", "comp-bar"]
    bar = find_entry(impacted, "comp-bar")
    assert bar["reason"] == "transitive-guarantee"
    assert bar["via"] == "comp-foo"
    assert bar["guarantee_ids"] == ["G-FOO-001"]
    foo = find_entry(impacted, "comp-foo")
    assert foo["reason"] == "direct"
    assert foo["via"] is None
    assert "guarantee_ids" not in foo


def test_cli_text_includes_bar_for_declared_changed_guarantee(tmp_path, capsys):
    build_repo(tmp_path)
    code = impact_analyzer.main(
        ["--changed", "comp-foo", "--repo-root=" + str(tmp_path)])
    out = capsys.readouterr().out
    assert code == 0
    lines = [line for line in out.splitlines() if line.strip()]
    assert lines == [
        "comp-foo\tdirect",
        "comp-bar\ttransitive-guarantee\tvia comp-foo\tG-FOO-001",
    ]