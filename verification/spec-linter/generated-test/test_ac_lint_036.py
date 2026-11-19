# hotdocs-criterion: sha256:005e04446b7892a69e1122143bcbe27c49410fcc24f80e0dfb69397aa37aee01
"""AC-LINT-036 (covers R-LINT-014): no glossary-split finding when a split is
recorded at architecture level, or when there is only one glossary file."""

from pathlib import Path

import spec_linter


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


GLOSSARY_MAIN = (
    "# Glossary\n"
    "\n"
    "Canonical vocabulary for the core subsystem.\n"
    "\n"
    "- **Widget** — a unit of work handled by the core subsystem.\n"
    "- **Gadget** — a helper used by widgets.\n"
)

GLOSSARY_BILLING = (
    "# Billing Glossary\n"
    "\n"
    "Canonical vocabulary for the billing subsystem.\n"
    "\n"
    "- **Invoice** — a bill issued to a customer.\n"
    "- **Ledger** — the record of all invoices and payments.\n"
)

ARCH_SPLIT = (
    "---\n"
    "id: arch-glossary-bounded-contexts\n"
    "title: Glossary Bounded-Context Split\n"
    "status: draft\n"
    "owners: [pipeline-team]\n"
    "---\n"
    "\n"
    "# Glossary Bounded-Context Split\n"
    "\n"
    "## Purpose\n"
    "\n"
    "This architecture decision records a bounded-context split of the\n"
    "glossary. The core subsystem and the billing subsystem genuinely do\n"
    "not share vocabulary, so the glossary is split into two bounded\n"
    "contexts: `specs/glossary.md` for the core bounded context and\n"
    "`specs/glossary-billing.md` for the billing bounded context.\n"
    "\n"
    "## Decision\n"
    "\n"
    "Bounded-context split: `glossary.md` (core) and `glossary-billing.md`\n"
    "(billing). This split is a deliberate architecture-level\n"
    "bounded-context decision, not a response to word count.\n"
)


def _r014_findings(report):
    return [
        f for f in field(report, "findings")
        if field(f, "rule_id") == "R-LINT-014"
    ]


def test_two_glossaries_with_architecture_split_has_no_r_lint_014(tmp_path):
    repo_root = tmp_path / "repo"
    _write(repo_root / "specs" / "glossary.md", GLOSSARY_MAIN)
    _write(repo_root / "specs" / "glossary-billing.md", GLOSSARY_BILLING)
    _write(
        repo_root / "specs" / "architecture" / "glossary-bounded-contexts.md",
        ARCH_SPLIT,
    )

    report = spec_linter.lint(None, repo_root)

    found = _r014_findings(report)
    assert found == [], "unexpected R-LINT-014 findings: " + repr(found)


def test_single_glossary_without_architecture_file_has_no_r_lint_014(tmp_path):
    repo_root = tmp_path / "repo"
    _write(repo_root / "specs" / "glossary.md", GLOSSARY_MAIN)

    report = spec_linter.lint(None, repo_root)

    found = _r014_findings(report)
    assert found == [], "unexpected R-LINT-014 findings: " + repr(found)


def test_control_two_glossaries_without_split_decision_fails(tmp_path):
    # Control for R-LINT-014 itself: the same two glossary files with no
    # architecture-level split decision MUST produce a failing finding, so
    # the absence asserted above is meaningful.
    repo_root = tmp_path / "repo"
    _write(repo_root / "specs" / "glossary.md", GLOSSARY_MAIN)
    _write(repo_root / "specs" / "glossary-billing.md", GLOSSARY_BILLING)

    report = spec_linter.lint(None, repo_root)

    found = _r014_findings(report)
    assert found, "expected an R-LINT-014 finding without a split decision"
    assert any(field(f, "severity") == "fail" for f in found)