# hotdocs-criterion: sha256:2c67a142980d184f3a02d68bdc213e26c09d97868b921e4ce859b9a20538ea54
"""AC-LINT-014: more than one glossary-like file under specs/ without an
architecture/-level bounded-context split decision is a fail finding for
R-LINT-014."""

from pathlib import Path

import spec_linter


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_fixture(repo_root: Path) -> None:
    specs = repo_root / "specs"

    # Primary corpus glossary: no frontmatter.
    write(
        specs / "glossary.md",
        "# Glossary\n"
        "\n"
        "Canonical vocabulary for this spec corpus.\n"
        "\n"
        "- **Widget** — a thing the system builds.\n",
    )

    # A second file that also declares itself a corpus glossary.
    write(
        specs / "glossary-billing.md",
        "# Glossary\n"
        "\n"
        "Canonical vocabulary for this spec corpus.\n"
        "\n"
        "- **Invoice** — a bill sent to a customer.\n",
    )

    # An architecture doc that records no split decision at all.
    write(
        specs / "architecture" / "overview.md",
        "---\n"
        "id: arch-overview\n"
        "title: Overview\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "depends_on: []\n"
        "---\n"
        "\n"
        "# Overview\n"
        "\n"
        "How the components fit together. Nothing about vocabulary.\n",
    )


def test_ac_lint_014_second_glossary_without_split_decision_fails(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root)

    report = spec_linter.lint(None, repo_root)

    findings = list(field(report, "findings"))
    lint_014 = [f for f in findings if field(f, "rule_id") == "R-LINT-014"]
    fails = [f for f in lint_014 if field(f, "severity") == "fail"]

    assert fails, (
        "expected a fail-severity R-LINT-014 finding; got findings: "
        + repr([(field(f, "rule_id"), field(f, "severity"), field(f, "file"))
                for f in findings])
    )

    # Each glossary-like file but specs/glossary.md gets one finding.
    files = [str(field(f, "file")).replace("\\", "/") for f in fails]
    assert any(p.endswith("glossary-billing.md") for p in files), files
    assert not any(
        p.endswith("specs/glossary.md") or p == "glossary.md" for p in files
    ), files

    assert field(report, "hard_failures") >= 1