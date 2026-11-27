# hotdocs-criterion: sha256:d379461e0d3472381d17f038cd70a5c40968a7a6e6578566fc3a93cc0719bed3
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


def write_component(repo, slug, depends_on=None):
    upper = slug.upper()
    title = slug.title()
    base = repo / "specs" / "components" / slug
    fm_lines = [
        "---",
        "id: comp-" + slug,
        "title: " + title,
        "status: draft",
        "owners: [test-team]",
        "sealed: true",
        "source_path: legacy/" + slug + "/",
    ]
    if depends_on:
        fm_lines.append("depends_on: [" + ", ".join(depends_on) + "]")
    fm_lines.append("---")
    body_lines = ["", "# " + title]
    for section in [
        "Purpose", "Scope", "Definitions", "Behavior", "Interfaces",
        "Acceptance criteria", "Open questions", "Change log",
    ]:
        body_lines.append("")
        body_lines.append("## " + section)
        body_lines.append("")
        body_lines.append("Placeholder text for " + section.lower() + ".")
    write(base / "component.md", "\n".join(fm_lines + body_lines) + "\n")

    req_id = "R-" + upper + "-001"
    ac_id = "AC-" + upper + "-001"
    write(base / "requirements" / (req_id + ".md"),
          "# " + req_id + "\n\nThe component MUST return its input unchanged.\n")
    write(base / "acceptance" / (ac_id + ".md"),
          "# " + ac_id + "\n"
          "\n"
          "Covers: " + req_id + "\n"
          "Kind: generated-test\n"
          "\n"
          "```gherkin\n"
          "Given 1\n"
          "When it runs\n"
          "Then it returns 1\n"
          "```\n")
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


def test_ac_impact_012(tmp_path, monkeypatch, capsys):
    repo = tmp_path
    write(repo / "specs" / "glossary.md",
          "# Glossary\n\n- **Fixture** — a test component.\n")
    write_component(repo, "foo")
    write_component(repo, "bar", depends_on=["comp-foo"])

    git(repo, "init", "-q", "-b", "main")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "A")
    git(repo, "switch", "-q", "-c", "feature")

    spec_linter = load_spec_linter()
    assert spec_linter.lint(None, repo).hard_failures == 0

    monkeypatch.chdir(repo / "specs")
    capsys.readouterr()

    code = impact_analyzer.main(["--changed", "comp-foo", "--format=json"])
    captured = capsys.readouterr()

    assert code == 0, "stdout=" + repr(captured.out) + " stderr=" + repr(captured.err)
    report = json.loads(captured.out)
    assert field(report, "precondition_error") is None
    impacted = field(report, "impacted")
    foo_entries = [e for e in impacted if field(e, "component_id") == "comp-foo"]
    assert len(foo_entries) == 1, repr(impacted)
    assert field(foo_entries[0], "reason") == "direct"
    assert field(foo_entries[0], "via") is None