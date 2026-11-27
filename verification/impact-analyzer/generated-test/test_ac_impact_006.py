# hotdocs-criterion: sha256:bf65a69c3ece0820a773eaac63754e7b153c2e4adfbd5efa27efae746ff19b75
"""AC-IMPACT-006: two consecutive runs of `hotdocs impact` over an unchanged
corpus with the same --changed argument produce byte-identical output."""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import impact_analyzer


GIT_PREFIX = [
    "git",
    "-c",
    "user.name=hotdocs-test",
    "-c",
    "user.email=test@example.com",
    "-c",
    "commit.gpgsign=false",
]


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def git(repo, *args):
    subprocess.run(
        GIT_PREFIX + list(args),
        cwd=str(repo),
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


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
    if depends_on:
        lines.append("depends_on: [" + ", ".join(depends_on) + "]")
    lines.append("---")
    lines.append("")
    lines.append("# " + title)
    for section in [
        "Purpose",
        "Scope",
        "Definitions",
        "Behavior",
        "Interfaces",
        "Acceptance criteria",
        "Open questions",
        "Change log",
    ]:
        lines.append("")
        lines.append("## " + section)
        lines.append("")
        lines.append("Fixture text for " + section.lower() + ".")
    return "\n".join(lines) + "\n"


def library_md(signature):
    return "# Library\n\n```\n" + signature + "\n```\n"


def write_component(repo, slug, depends_on=None, signature="run(x: int) -> int"):
    upper = slug.upper()
    root = repo / "specs" / "components" / slug
    write(root / "component.md", component_md(slug, depends_on))
    write(
        root / "requirements" / ("R-" + upper + "-001.md"),
        "# R-" + upper + "-001\n\nThe component MUST return its input unchanged.\n",
    )
    write(
        root / "acceptance" / ("AC-" + upper + "-001.md"),
        "# AC-"
        + upper
        + "-001\n\nCovers: R-"
        + upper
        + "-001\nKind: generated-test\n\n```gherkin\nGiven 1\nWhen it runs\nThen it returns 1\n```\n",
    )
    write(
        root / "constraints.md",
        "# Constraints\n\n- The component MUST finish within 1 second.\n",
    )
    write(root / "interface" / "library.md", library_md(signature))


def load_spec_linter():
    gen = next(
        p for p in Path(impact_analyzer.__file__).resolve().parents if p.name == "gen"
    )
    base = gen / "spec-linter"
    path = (
        base / "spec_linter.py"
        if (base / "spec_linter.py").is_file()
        else base / "spec_linter" / "__init__.py"
    )
    spec = importlib.util.spec_from_file_location("spec_linter", path)
    spec_linter = importlib.util.module_from_spec(spec)
    sys.modules["spec_linter"] = spec_linter
    spec.loader.exec_module(spec_linter)
    return spec_linter


def build_repo(repo):
    write(
        repo / "specs" / "glossary.md",
        "# Glossary\n\n- **Fixture** — a test component.\n",
    )
    write_component(repo, "alpha")
    write_component(repo, "beta", depends_on=["comp-alpha"])
    write_component(repo, "gamma")

    git(repo, "init", "-q", "-b", "main")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "A")
    git(repo, "switch", "-q", "-c", "feature")

    # Changed state: alpha's interface signature changes (left uncommitted).
    write(
        repo / "specs" / "components" / "alpha" / "interface" / "library.md",
        library_md("run(x: int, y: int) -> int"),
    )


def run_twice(capsys, argv):
    capsys.readouterr()
    code1 = impact_analyzer.main(list(argv))
    out1 = capsys.readouterr()
    code2 = impact_analyzer.main(list(argv))
    out2 = capsys.readouterr()
    return code1, out1, code2, out2


def test_ac_impact_006_two_runs_byte_identical(tmp_path, capsys, monkeypatch):
    repo = tmp_path
    build_repo(repo)
    monkeypatch.chdir(repo)

    spec_linter = load_spec_linter()
    assert spec_linter.lint(None, repo).hard_failures == 0

    # JSON format
    argv_json = ["--changed", "comp-alpha", "--repo-root", str(repo), "--format=json"]
    code1, out1, code2, out2 = run_twice(capsys, argv_json)
    assert code1 == 0, out1.err
    assert code2 == 0, out2.err
    assert out1.out != ""
    assert out1.out.encode("utf-8") == out2.out.encode("utf-8")

    report = json.loads(out1.out)
    impacted = field(report, "impacted")
    assert field(report, "precondition_error") is None
    ids = [field(e, "component_id") for e in impacted]
    assert "comp-alpha" in ids
    alpha = next(e for e in impacted if field(e, "component_id") == "comp-alpha")
    assert field(alpha, "reason") == "direct"

    # Text format
    argv_text = ["--changed", "comp-alpha", "--repo-root", str(repo), "--format=text"]
    code1, out1, code2, out2 = run_twice(capsys, argv_text)
    assert code1 == 0, out1.err
    assert code2 == 0, out2.err
    assert out1.out != ""
    assert out1.out.encode("utf-8") == out2.out.encode("utf-8")

    # Library: two consecutive calls yield identical serialized reports.
    r1 = impact_analyzer.compute_blast_radius(["comp-alpha"], repo)
    r2 = impact_analyzer.compute_blast_radius(["comp-alpha"], repo)
    d1 = r1.to_dict() if hasattr(r1, "to_dict") else r1
    d2 = r2.to_dict() if hasattr(r2, "to_dict") else r2
    assert json.dumps(d1, sort_keys=False).encode("utf-8") == json.dumps(
        d2, sort_keys=False
    ).encode("utf-8")