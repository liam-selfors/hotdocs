# hotdocs-criterion: sha256:005e04446b7892a69e1122143bcbe27c49410fcc24f80e0dfb69397aa37aee01
"""AC-LINT-036 (covers R-LINT-014).

A glossary split under specs/ is legitimate only when an architecture-level
bounded-context split decision records it. A lone specs/glossary.md is
always fine.
"""

from pathlib import Path

import spec_linter


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


MAIN_GLOSSARY = (
    "# Glossary\n"
    "\n"
    "Canonical vocabulary for this spec corpus.\n"
    "\n"
    "- **Component** — a unit of generated code with its own spec directory.\n"
    "- **Gate** — one verification step in the pipeline.\n"
)

BILLING_GLOSSARY = (
    "# Glossary (billing bounded context)\n"
    "\n"
    "Vocabulary for the billing subsystem only.\n"
    "\n"
    "- **Invoice** — a statement of charges issued to a customer.\n"
    "- **Ledger entry** — one immutable debit or credit record.\n"
)

ARCH_SPLIT_DOC = (
    "---\n"
    "id: arch-glossary-bounded-contexts\n"
    "title: Glossary Bounded-Context Split\n"
    "status: draft\n"
    "owners: [pipeline-team]\n"
    "---\n"
    "\n"
    "# Glossary bounded-context split\n"
    "\n"
    "## Purpose\n"
    "\n"
    "This architecture decision records a deliberate bounded-context split\n"
    "of the glossary. The billing subsystem and the core pipeline do not\n"
    "share vocabulary, so the glossary is split into two bounded contexts:\n"
    "`specs/glossary.md` (core) and `specs/glossary-billing.md` (billing).\n"
    "\n"
    "## Decision\n"
    "\n"
    "Split the glossary by bounded context: glossary.md holds the core\n"
    "bounded context, glossary-billing.md holds the billing bounded context.\n"
    "This bounded-context split is an architecture-level decision, not a\n"
    "routine response to word count.\n"
)


def _rule_ids(report):
    return [field(f, "rule_id") for f in field(report, "findings")]


def test_two_glossaries_with_architecture_split_decision_has_no_r_lint_014(tmp_path):
    repo_root = tmp_path
    _write(repo_root / "specs" / "glossary.md", MAIN_GLOSSARY)
    _write(repo_root / "specs" / "glossary-billing.md", BILLING_GLOSSARY)
    _write(
        repo_root / "specs" / "architecture" / "glossary-bounded-contexts.md",
        ARCH_SPLIT_DOC,
    )

    report = spec_linter.lint(None, repo_root)

    ids = _rule_ids(report)
    assert "R-LINT-014" not in ids, (
        "unexpected R-LINT-014 finding despite a recorded bounded-context "
        "split: " + repr([f for f in field(report, "findings")
                          if field(f, "rule_id") == "R-LINT-014"])
    )


def test_single_glossary_without_architecture_file_has_no_r_lint_014(tmp_path):
    repo_root = tmp_path
    _write(repo_root / "specs" / "glossary.md", MAIN_GLOSSARY)
    (repo_root / "specs" / "architecture").mkdir(parents=True, exist_ok=True)

    report = spec_linter.lint(None, repo_root)

    ids = _rule_ids(report)
    assert "R-LINT-014" not in ids, (
        "unexpected R-LINT-014 finding with only one glossary: "
        + repr([f for f in field(report, "findings")
                if field(f, "rule_id") == "R-LINT-014"])
    )


def test_control_two_glossaries_without_split_decision_is_flagged(tmp_path):
    # Control: R-LINT-014 MUST fail when more than one glossary-like file
    # exists without an architecture-level split decision, so the absence
    # asserted above is meaningful rather than vacuous.
    repo_root = tmp_path
    _write(repo_root / "specs" / "glossary.md", MAIN_GLOSSARY)
    _write(repo_root / "specs" / "glossary-billing.md", BILLING_GLOSSARY)

    report = spec_linter.lint(None, repo_root)

    matching = [f for f in field(report, "findings")
                if field(f, "rule_id") == "R-LINT-014"]
    assert matching, "expected an R-LINT-014 finding with two glossaries and no split decision"
    assert all(field(f, "severity") == "fail" for f in matching)
    assert field(report, "hard_failures") >= 1