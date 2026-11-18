# hotdocs-criterion: sha256:005e04446b7892a69e1122143bcbe27c49410fcc24f80e0dfb69397aa37aee01
"""AC-LINT-036 (covers R-LINT-014).

More than one glossary-like file under specs/ is allowed only when an
architecture/-level bounded-context split decision records it; a single
glossary needs no such decision at all.
"""

from pathlib import Path

import spec_linter


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _main_glossary(repo_root):
    _write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n"
        "\n"
        "Canonical vocabulary for the core subsystem.\n"
        "\n"
        "- **Widget** — a unit of core work.\n"
        "- **Gadget** — a tool that processes widgets.\n",
    )


def _billing_glossary(repo_root):
    _write(
        repo_root / "specs" / "glossary-billing.md",
        "# Billing glossary\n"
        "\n"
        "Canonical vocabulary for the billing bounded context.\n"
        "\n"
        "- **Invoice** — a request for payment.\n"
        "- **Ledger** — the record of all billing transactions.\n",
    )


def _split_decision(repo_root):
    _write(
        repo_root / "specs" / "architecture" / "glossary-bounded-contexts.md",
        "---\n"
        "id: arch-glossary-bounded-contexts\n"
        "title: Glossary bounded-context split\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "---\n"
        "\n"
        "# Glossary bounded-context split\n"
        "\n"
        "## Decision\n"
        "\n"
        "This is the architecture-level bounded-context split decision for the\n"
        "glossary. The core and billing subsystems genuinely do not share\n"
        "vocabulary, so the glossary is split into two bounded contexts:\n"
        "\n"
        "- `specs/glossary.md` — the core bounded context.\n"
        "- `specs/glossary-billing.md` — the billing bounded context.\n"
        "\n"
        "This bounded-context split of the glossary is deliberate, not a\n"
        "response to word count.\n",
    )


def _r_lint_014_findings(report):
    return [f for f in field(report, "findings") if field(f, "rule_id") == "R-LINT-014"]


def test_two_glossaries_with_bounded_context_split_decision_no_finding(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _main_glossary(repo_root)
    _billing_glossary(repo_root)
    _split_decision(repo_root)

    report = spec_linter.lint(None, repo_root)

    found = _r_lint_014_findings(report)
    assert found == [], "unexpected R-LINT-014 findings: " + repr(found)


def test_single_glossary_without_architecture_file_no_finding(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _main_glossary(repo_root)
    assert not (repo_root / "specs" / "architecture").exists()

    report = spec_linter.lint(None, repo_root)

    found = _r_lint_014_findings(report)
    assert found == [], "unexpected R-LINT-014 findings: " + repr(found)


def test_control_two_glossaries_without_split_decision_fails(tmp_path):
    # Control: the rule is actually live — the same two glossaries with no
    # architecture-level split decision do produce an R-LINT-014 failure,
    # so the absence asserted above is due to the decision, not a dead rule.
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _main_glossary(repo_root)
    _billing_glossary(repo_root)

    report = spec_linter.lint(None, repo_root)

    found = _r_lint_014_findings(report)
    assert found, "expected an R-LINT-014 finding without a split decision"
    assert any(field(f, "severity") == "fail" for f in found)