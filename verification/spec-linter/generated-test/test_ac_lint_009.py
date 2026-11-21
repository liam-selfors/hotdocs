# hotdocs-criterion: sha256:e1dd896ed62011c5c068879f7c2e9520fe2641c595e297d55fa9d316855081e2
import json
from pathlib import Path

import spec_linter


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


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
    "```gherkin\n"
    "Given nothing\n"
    "When a foo is made\n"
    "Then it exists\n"
    "```\n"
)

COMPONENT_MD = (
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

R_FOO_001 = (
    "# R-FOO-001\n"
    "\n"
    "**R-FOO-001** \u2014 `make_foo()` MUST return the string `\"foo\"`.\n"
)

LIBRARY_MD = (
    "# Library\n"
    "\n"
    "One module file, `foo.py`.\n"
    "\n"
    "```\n"
    "make_foo() -> str\n"
    "```\n"
)

AC_FOO_001 = (
    "# AC-FOO-001\n"
    "\n"
    "Covers: R-FOO-001\n"
    "Kind: generated-test\n"
    "\n"
    "```gherkin\n"
    "Given nothing\n"
    "When make_foo() is called\n"
    "Then the result is \"foo\"\n"
    "```\n"
)

AC_FOO_002_DANGLING = (
    "# AC-FOO-002\n"
    "\n"
    "Covers: R-DOES-NOT-EXIST\n"
    "Kind: generated-test\n"
    "\n"
    "```gherkin\n"
    "Given nothing\n"
    "When make_foo() is called\n"
    "Then the result is a string\n"
    "```\n"
)

CONSTRAINTS_MD = (
    "# Foo \u2014 Non-Functional Constraints\n"
    "\n"
    "- **Pure.** No I/O.\n"
)


def write(root, rel, text):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def build_clean_corpus(repo_root):
    write(repo_root, "specs/product/foo.md", PRODUCT_FOO)
    write(repo_root, "specs/components/foo/component.md", COMPONENT_MD)
    write(repo_root, "specs/components/foo/requirements/R-FOO-001.md", R_FOO_001)
    write(repo_root, "specs/components/foo/interface/library.md", LIBRARY_MD)
    write(repo_root, "specs/components/foo/acceptance/AC-FOO-001.md", AC_FOO_001)
    write(repo_root, "specs/components/foo/constraints.md", CONSTRAINTS_MD)


def r_lint_009_fails(findings):
    return [
        f
        for f in findings
        if field(f, "rule_id") == "R-LINT-009" and field(f, "severity") == "fail"
    ]


def test_clean_corpus_has_no_r_lint_009_finding(tmp_path):
    repo_root = tmp_path / "repo"
    build_clean_corpus(repo_root)
    report = spec_linter.lint(None, repo_root)
    assert field(report, "hard_failures") == 0
    assert r_lint_009_fails(field(report, "findings")) == []


def test_dangling_covers_tag_is_fail_finding_for_r_lint_009(tmp_path):
    repo_root = tmp_path / "repo"
    build_clean_corpus(repo_root)
    write(
        repo_root,
        "specs/components/foo/acceptance/AC-FOO-002.md",
        AC_FOO_002_DANGLING,
    )

    report = spec_linter.lint(None, repo_root)
    findings = field(report, "findings")
    matching = r_lint_009_fails(findings)
    assert matching, "expected a fail-severity R-LINT-009 finding, got: " + repr(
        [(field(f, "rule_id"), field(f, "severity"), field(f, "message")) for f in findings]
    )
    assert field(report, "hard_failures") >= 1


def test_dangling_covers_tag_cli_json_reports_r_lint_009_and_exits_1(tmp_path, capsys):
    repo_root = tmp_path / "repo"
    build_clean_corpus(repo_root)
    write(
        repo_root,
        "specs/components/foo/acceptance/AC-FOO-002.md",
        AC_FOO_002_DANGLING,
    )

    code = spec_linter.main(["--format=json", "--repo-root=" + str(repo_root)])
    out = capsys.readouterr().out
    assert code == 1
    doc = json.loads(out)
    matching = [
        f
        for f in doc["findings"]
        if f["rule_id"] == "R-LINT-009" and f["severity"] == "fail"
    ]
    assert matching
    assert doc["summary"]["hard_failures"] >= 1