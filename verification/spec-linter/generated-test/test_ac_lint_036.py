# hotdocs-criterion: sha256:558f9814df2d85dcbcc00426bb9d8627820bde08de37f1212b94d2876da5f0b6
from pathlib import Path

import pytest

import spec_linter


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


GLOSSARY = (
    "# Glossary\n"
    "\n"
    "Canonical vocabulary.\n"
    "\n"
    "- **Widget** — a thing the system manages.\n"
)

BILLING_GLOSSARY = (
    "# Billing Glossary\n"
    "\n"
    "Vocabulary of the billing subsystem.\n"
    "\n"
    "- **Invoice** — a bill sent to a customer.\n"
)


def architecture_doc(phrase: str) -> str:
    return (
        "---\n"
        "id: arch-glossary-split\n"
        "title: Glossary Split\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "depends_on: []\n"
        "---\n"
        "\n"
        "# Glossary Split\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Billing and the core pipeline do not share vocabulary, so the glossary\n"
        "is split along a " + phrase + " line: specs/glossary.md for the core,\n"
        "specs/glossary-billing.md for billing.\n"
    )


def r014_findings(report):
    findings = field(report, "findings")
    return [f for f in findings if field(f, "rule_id") == "R-LINT-014"]


@pytest.mark.parametrize("phrase", ["bounded context", "bounded-context", "Bounded-Context"])
def test_two_glossaries_with_bounded_context_split_has_no_r_lint_014(tmp_path, phrase):
    repo_root = tmp_path
    write(repo_root / "specs" / "glossary.md", GLOSSARY)
    write(repo_root / "specs" / "glossary-billing.md", BILLING_GLOSSARY)
    write(repo_root / "specs" / "architecture" / "glossary-split.md", architecture_doc(phrase))

    report = spec_linter.lint(None, repo_root)

    assert r014_findings(report) == []


def test_single_glossary_without_architecture_file_has_no_r_lint_014(tmp_path):
    repo_root = tmp_path
    write(repo_root / "specs" / "glossary.md", GLOSSARY)

    report = spec_linter.lint(None, repo_root)

    assert r014_findings(report) == []


def test_two_glossaries_without_split_decision_is_flagged(tmp_path):
    # Sanity check from R-LINT-014 itself: without a bounded-context
    # architecture doc, each glossary file but specs/glossary.md is flagged.
    repo_root = tmp_path
    write(repo_root / "specs" / "glossary.md", GLOSSARY)
    write(repo_root / "specs" / "glossary-billing.md", BILLING_GLOSSARY)

    report = spec_linter.lint(None, repo_root)

    found = r014_findings(report)
    assert len(found) == 1
    assert str(field(found[0], "file")).replace("\\", "/").endswith("glossary-billing.md")
    assert field(found[0], "severity") == "fail"