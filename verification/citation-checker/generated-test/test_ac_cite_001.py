# hotdocs-criterion: sha256:afeb4d6bf0c3f4d7447f7acffc40b9ce6548d6e2178d1cb28845b67befe0aaaf
from pathlib import Path

import citation_checker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def make_component(repo_root, slug, body_text):
    base = repo_root / "specs" / "components" / slug
    upper = slug.upper()
    write(
        base / "component.md",
        "---\n"
        + "id: comp-" + slug + "\n"
        + "title: " + slug.capitalize() + " Component\n"
        + "status: draft\n"
        + "owners: [pipeline-team]\n"
        + "depends_on: []\n"
        + "sealed: true\n"
        + "source_path: legacy/" + slug + "/\n"
        + "---\n"
        + "\n"
        + "# " + slug.capitalize() + " Component\n"
        + "\n"
        + body_text
        + "\n",
    )
    write(
        base / "requirements" / ("R-" + upper + "-001.md"),
        "# R-" + upper + "-001\n"
        + "\n"
        + "**R-" + upper + "-001** — The component MUST return a value.\n",
    )
    write(
        base / "acceptance" / ("AC-" + upper + "-001.md"),
        "# AC-" + upper + "-001\n"
        + "\n"
        + "Covers: R-" + upper + "-001\n"
        + "Kind: generated-test\n"
        + "\n"
        + "```gherkin\n"
        + "Given the component\n"
        + "When it runs\n"
        + "Then it returns a value\n"
        + "```\n",
    )


def build_fixture(repo_root):
    write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n"
        + "\n"
        + "- **Widget** — a small thing used in tests.\n",
    )
    # First: cites a decision number with no specs/decisions/ file.
    make_component(
        repo_root,
        "alpha",
        "This behavior follows `D999`, which was decided long ago.\n",
    )
    # Second: cites D7 from notes/initial-ideas.md's informal D1-D14 numbering.
    make_component(
        repo_root,
        "beta",
        "This behavior follows D7 in `notes/initial-ideas.md`, its informal "
        "numbering never formalized as a decision file.\n",
    )


def test_ac_cite_001_only_unresolved_formal_citation_flagged(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root)

    findings = citation_checker.check(repo_root)

    cite_findings = [f for f in findings if field(f, "rule_id") == "R-CITE-001"]

    alpha_file = "specs/components/alpha/component.md"
    beta_file = "specs/components/beta/component.md"

    files = [str(field(f, "file")).replace("\\", "/") for f in cite_findings]

    assert alpha_file in files, cite_findings
    assert beta_file not in files, cite_findings
    assert all(p == alpha_file for p in files), cite_findings
    assert len(cite_findings) == 1, cite_findings

    only = cite_findings[0]
    assert field(only, "severity") in ("fail", "warn")
    assert isinstance(field(only, "line"), int)
    assert isinstance(field(only, "message"), str)