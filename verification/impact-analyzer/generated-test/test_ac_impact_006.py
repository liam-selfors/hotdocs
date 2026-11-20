# hotdocs-criterion: sha256:237bdabb72841172eb7f745b59c8c4b46dab1baf34cb65604ed53383cfb720f6
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
    for section in ["Purpose", "Scope", "Definitions", "Behavior", "Interfaces",
                    "Acceptance criteria", "Open questions", "Change log"]:
        body.append("")
        body.append("## " + section)
        body.append("")
        if section == "Open questions":
            body.append("None.")
        else:
            body.append("The " + section.lower() + " of this fixture component.")
    write(base / "component.md", "\n".join(fm + body) + "\n")
    write(base / "requirements" / ("R-" + upper + "-001.md"),
          "# R-" + upper + "-001\n\nThe component MUST return its input unchanged.\n")
    write(base / "acceptance" / ("AC-" + upper + "-001.md"),
          "# AC-" + upper + "-001\n\nCovers: R-" + upper + "-001\nKind: generated-test\n\n"
          "```gherkin\nGiven 1\nWhen it runs\nThen it returns 1\n```\n")
    write(base / "constraints.md",
          "# Constraints\n\n- The component MUST finish within 1 second.\n")
    write(base / "interface" / "library.md",
          "# Library\n\n```\n" + signature + "\n```\n")


def load_spec_linter():
    gen = next(p for p in Path(impact_analyzer.__file__).resolve().parents if p.name == "gen")
    base = gen / "spec-linter"
    path = base / "spec_linter.py" if (base / "spec_linter.py").is_file() else base / "spec_linter" / "__init__.py"
    spec = importlib.util.spec_from_file_location("spec_linter", path)
    spec_linter = importlib.util.module_from_spec(spec)
    sys.modules["spec_linter"] = spec_linter
    spec.loader.exec_module(spec_linter)
    return spec_linter


def build_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    write(repo / "specs" / "glossary.md",
          "# Glossary\n\n- **Fixture** — a test component.\n")
    write_component(repo, "foo")
    write_component(repo, "bar", depends_on=["comp-foo"])
    write_component(repo, "baz", depends_on=["comp-bar"])
    git(repo, "init", "-q", "-b", "main")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "A")
    git(repo, "switch", "-q", "-c", "feature")
    # Changed state: foo's interface signature changes (uncommitted).
    write(repo / "specs" / "components" / "foo" / "interface" / "library.md",
          "# Library\n\n```\nrun(x: int, y: int) -> int\n```\n")
    return repo


def run_cli(capsys, argv):
    capsys.readouterr()
    code = impact_analyzer.main(argv)
    out, err = capsys.readouterr()
    return code, out, err


def test_ac_impact_006_json_runs_are_byte_identical(tmp_path, capsys):
    repo = build_repo(tmp_path)
    spec_linter = load_spec_linter()
    assert spec_linter.lint(None, repo).hard_failures == 0

    argv = ["--changed", "comp-foo", "--repo-root", str(repo), "--format=json"]
    code1, out1, _ = run_cli(capsys, list(argv))
    code2, out2, _ = run_cli(capsys, list(argv))

    assert code1 == 0
    assert code2 == 0
    assert out1.encode("utf-8") == out2.encode("utf-8")

    report = json.loads(out1)
    assert report["precondition_error"] is None
    ids = [entry["component_id"] for entry in report["impacted"]]
    assert "comp-foo" in ids
    assert len(ids) >= 2


def test_ac_impact_006_text_runs_are_byte_identical(tmp_path, capsys):
    repo = build_repo(tmp_path)
    spec_linter = load_spec_linter()
    assert spec_linter.lint(None, repo).hard_failures == 0

    argv = ["--changed", "comp-foo", "comp-bar", "--repo-root=" + str(repo), "--format", "text"]
    code1, out1, _ = run_cli(capsys, list(argv))
    code2, out2, _ = run_cli(capsys, list(argv))

    assert code1 == 0
    assert code2 == 0
    assert out1 != ""
    assert out1.encode("utf-8") == out2.encode("utf-8")


def test_ac_impact_006_library_reports_identical(tmp_path):
    repo = build_repo(tmp_path)
    spec_linter = load_spec_linter()
    assert spec_linter.lint(None, repo).hard_failures == 0

    r1 = impact_analyzer.compute_blast_radius(["comp-foo"], repo)
    r2 = impact_analyzer.compute_blast_radius(["comp-foo"], repo)

    assert field(r1, "precondition_error") is None
    assert field(r2, "precondition_error") is None
    d1 = r1.to_dict() if not isinstance(r1, dict) else r1
    d2 = r2.to_dict() if not isinstance(r2, dict) else r2
    s1 = json.dumps(d1, sort_keys=False).encode("utf-8")
    s2 = json.dumps(d2, sort_keys=False).encode("utf-8")
    assert s1 == s2
    assert len(field(r1, "impacted")) >= 1