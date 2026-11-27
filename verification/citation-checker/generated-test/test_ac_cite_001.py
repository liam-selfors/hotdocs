# hotdocs-criterion: sha256:bebf8f01f0b11512cd7caaefe47be6de519409258289decbc97fe7879b5cdeeb
from pathlib import Path

import citation_checker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def component_md(slug, title, body):
    return (
        "---\n"
        "id: comp-" + slug + "\n"
        "title: " + title + "\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "depends_on: []\n"
        "sealed: true\n"
        "source_path: legacy/" + slug + "/\n"
        "---\n"
        "\n"
        "# " + title + "\n"
        "\n"
        + body
    )


def decision_md(n):
    return (
        "---\n"
        "id: D" + str(n) + "\n"
        "title: Decision " + str(n) + "\n"
        "status: ratified\n"
        "last_ratified_commit: 0000000\n"
        "owners: [pipeline-team]\n"
        "---\n"
        "\n"
        "# D" + str(n) + "\n"
        "\n"
        "A real decision record.\n"
    )


def build_fixture(repo_root):
    specs = repo_root / "specs"
    write(specs / "glossary.md", "# Glossary\n\n- **Widget** — a thing.\n")
    # One real decision record, so specs/decisions/ exists but has no D9999 or D7.
    write(specs / "decisions" / "D500.md", decision_md(500))

    write(
        specs / "components" / "alpha" / "component.md",
        component_md(
            "alpha",
            "Alpha",
            "Alpha stores widgets as described by D9999, which picked the format.\n",
        ),
    )
    write(
        specs / "components" / "beta" / "component.md",
        component_md(
            "beta",
            "Beta",
            "Beta follows D7 of `notes/initial-ideas.md`, whose informal\n"
            "numbering was never formalized as decision files.\n",
        ),
    )


def test_ac_cite_001_only_unresolved_decision_citation_is_flagged(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root)

    findings = citation_checker.check(repo_root)
    assert isinstance(findings, list)

    cite_001 = [f for f in findings if field(f, "rule_id") == "R-CITE-001"]

    alpha_rel = "specs/components/alpha/component.md"
    beta_rel = "specs/components/beta/component.md"

    files = [str(field(f, "file")).replace("\\", "/") for f in cite_001]

    assert len(cite_001) == 1, cite_001
    assert files == [alpha_rel], cite_001
    assert beta_rel not in files

    finding = cite_001[0]
    assert field(finding, "severity") in ("fail", "warn")
    assert isinstance(field(finding, "line"), int)
    assert isinstance(field(finding, "message"), str)