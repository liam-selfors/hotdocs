# hotdocs-criterion: sha256:08f669ee5cd666c3fab6b90fbf1d1a1e826e5641aa9e9e0784caa6db35e89068
"""AC-LINT-036 (Covers: R-LINT-014).

Given specs/glossary.md and specs/glossary-billing.md, and a file under
specs/architecture/ whose body records a bounded-context split of the
glossary, lint(None, repo_root) reports no R-LINT-014 finding.

Given only specs/glossary.md and no such architecture file,
lint(None, repo_root) reports no R-LINT-014 finding.
"""

import spec_linter

from pathlib import Path


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


FENCE = "```"

PRODUCT_FOO = (
    "---\n"
    "id: P-FOO\n"
    "title: Foo works\n"
    "status: draft\n"
    "owners: [team-a]\n"
    "---\n"
    "\n"
    "# Foo works\n"
    "\n"
    "## Purpose\n"
    "\n"
    "A foo can be made.\n"
    "\n"
    "### CS-FOO-001\n"
    "Covers: P-FOO\n"
    "Kind: generated-test\n"
    "\n"
    + FENCE + "gherkin\n"
    "Given nothing\n"
    "When a foo is made\n"
    "Then it exists\n"
    + FENCE + "\n"
)

COMPONENT_FOO = (
    "---\n"
    "id: comp-foo\n"
    "title: Foo\n"
    "status: draft\n"
    "owners: [team-a]\n"
    "depends_on: []\n"
    "realizes: [P-FOO]\n"
    "sealed: false\n"
    "---\n"
    "\n"
    "# Foo\n"
    "\n"
    "## Purpose\n"
    "\n"
    "Makes a foo.\n"
    "\n"
    "## Scope\n"
    "\n"
    "**In scope:** making a foo. **Out of scope:** everything else.\n"
    "\n"
    "## Definitions\n"
    "\n"
    "No deltas from `specs/glossary.md`.\n"
    "\n"
    "## Behavior\n"
    "\n"
    "See `requirements/`.\n"
    "\n"
    "## Interfaces\n"
    "\n"
    "See `interface/`.\n"
    "\n"
    "## Data\n"
    "\n"
    "None.\n"
    "\n"
    "## Acceptance criteria\n"
    "\n"
    "See `acceptance/`.\n"
    "\n"
    "## Non-functional constraints\n"
    "\n"
    "See `constraints.md`.\n"
    "\n"
    "## Open questions\n"
    "\n"
    "None.\n"
    "\n"
    "## Change log\n"
    "\n"
    "- Initial draft.\n"
)

REQ_FOO = (
    "# R-FOO-001\n"
    "\n"
    "**R-FOO-001** \u2014 `make_foo()` MUST return the string `\"foo\"`.\n"
)

LIBRARY_FOO = (
    "# Library\n"
    "\n"
    "One module file, `foo.py`.\n"
    "\n"
    + FENCE + "\n"
    "make_foo() -> str\n"
    + FENCE + "\n"
)

AC_FOO = (
    "# AC-FOO-001\n"
    "\n"
    "Covers: R-FOO-001\n"
    "Kind: generated-test\n"
    "\n"
    + FENCE + "gherkin\n"
    "Given nothing\n"
    "When make_foo() is called\n"
    "Then the result is \"foo\"\n"
    + FENCE + "\n"
)

CONSTRAINTS_FOO = (
    "# Foo \u2014 Non-Functional Constraints\n"
    "\n"
    "- **Pure.** No I/O.\n"
)

GLOSSARY_MAIN = (
    "# Glossary\n"
    "\n"
    "Canonical vocabulary for this spec corpus.\n"
    "\n"
    "- **Foo** \u2014 the thing `comp-foo` makes.\n"
)

GLOSSARY_BILLING = (
    "# Billing Glossary\n"
    "\n"
    "Canonical vocabulary for the billing bounded context.\n"
    "\n"
    "- **Invoice** \u2014 a bill sent to a customer.\n"
)

ARCH_SPLIT = (
    "---\n"
    "id: arch-glossary-split\n"
    "title: Glossary Bounded-Context Split\n"
    "status: draft\n"
    "owners: [team-a]\n"
    "depends_on: []\n"
    "---\n"
    "\n"
    "# Glossary Bounded-Context Split\n"
    "\n"
    "## Purpose\n"
    "\n"
    "This architecture decision records a bounded-context split of the "
    "glossary: the billing subsystem and the core subsystem genuinely do "
    "not share vocabulary, so the glossary is split into two bounded "
    "contexts. `specs/glossary.md` holds the core bounded context's "
    "vocabulary and `specs/glossary-billing.md` holds the billing bounded "
    "context's vocabulary.\n"
    "\n"
    "## Decision\n"
    "\n"
    "Bounded-context split: `specs/glossary.md` (core) and "
    "`specs/glossary-billing.md` (billing).\n"
    "\n"
    "## Change log\n"
    "\n"
    "- Initial draft.\n"
)


def write(root, rel, text):
    path = Path(root) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def build_clean_corpus(root):
    write(root, "specs/product/foo.md", PRODUCT_FOO)
    write(root, "specs/components/foo/component.md", COMPONENT_FOO)
    write(root, "specs/components/foo/requirements/R-FOO-001.md", REQ_FOO)
    write(root, "specs/components/foo/interface/library.md", LIBRARY_FOO)
    write(root, "specs/components/foo/acceptance/AC-FOO-001.md", AC_FOO)
    write(root, "specs/components/foo/constraints.md", CONSTRAINTS_FOO)


def lint014_findings(report):
    findings = field(report, "findings")
    return [f for f in findings if field(f, "rule_id") == "R-LINT-014"]


def test_two_glossaries_with_architecture_split_has_no_r_lint_014(tmp_path):
    repo_root = tmp_path
    build_clean_corpus(repo_root)
    write(repo_root, "specs/glossary.md", GLOSSARY_MAIN)
    write(repo_root, "specs/glossary-billing.md", GLOSSARY_BILLING)
    write(repo_root, "specs/architecture/glossary-split.md", ARCH_SPLIT)

    report = spec_linter.lint(None, repo_root)

    assert lint014_findings(report) == []


def test_single_glossary_without_architecture_file_has_no_r_lint_014(tmp_path):
    repo_root = tmp_path
    build_clean_corpus(repo_root)
    write(repo_root, "specs/glossary.md", GLOSSARY_MAIN)

    assert not (repo_root / "specs" / "architecture").exists()

    report = spec_linter.lint(None, repo_root)

    assert lint014_findings(report) == []


def test_two_glossaries_without_split_decision_is_r_lint_014_failure(tmp_path):
    # Contrast case from R-LINT-014 itself: without the architecture-level
    # split decision, a second glossary-like file MUST fail.
    repo_root = tmp_path
    build_clean_corpus(repo_root)
    write(repo_root, "specs/glossary.md", GLOSSARY_MAIN)
    write(repo_root, "specs/glossary-billing.md", GLOSSARY_BILLING)

    report = spec_linter.lint(None, repo_root)

    found = lint014_findings(report)
    assert found, "expected an R-LINT-014 finding without a split decision"
    assert any(field(f, "severity") == "fail" for f in found)