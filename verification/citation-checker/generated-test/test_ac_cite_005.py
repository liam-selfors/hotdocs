# hotdocs-criterion: sha256:6bb015a6e2d3ce70146b0d223bb52f417eb8111f4bf2f3c3323cd992481913c8
from pathlib import Path

import citation_checker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def decision_source(doc_id, title, builds_on):
    return (
        "---\n"
        + "id: " + doc_id + "\n"
        + "title: " + title + "\n"
        + "status: draft\n"
        + "owners: [pipeline-team]\n"
        + "builds_on: [" + ", ".join(builds_on) + "]\n"
        + "---\n"
        + "\n"
        + "# " + doc_id + " " + title + "\n"
        + "\n"
        + "A decision record used as a test fixture.\n"
    )


def build_corpus(repo_root):
    specs = repo_root / "specs"
    write(
        specs / "glossary.md",
        "# Glossary\n"
        "\n"
        "- **Fixture term** — a term used only by this test fixture.\n",
    )
    write(
        specs / "decisions" / "D200.md",
        decision_source("D200", "Dangling builds on", ["D999"]),
    )
    write(
        specs / "decisions" / "D201.md",
        decision_source("D201", "Builds on informal decision", ["D7"]),
    )


def test_ac_cite_005_builds_on_unresolved_flagged_but_d1_to_d14_exempt(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_corpus(repo_root)

    findings = citation_checker.check(repo_root)
    assert isinstance(findings, list)

    cite5 = [f for f in findings if field(f, "rule_id") == "R-CITE-005"]

    assert len(cite5) == 1, cite5
    only = cite5[0]
    assert field(only, "file").replace("\\", "/") == "specs/decisions/D200.md"
    assert field(only, "severity") in ("fail", "warn")
    assert isinstance(field(only, "line"), int)

    flagged_files = [field(f, "file").replace("\\", "/") for f in cite5]
    assert "specs/decisions/D201.md" not in flagged_files