# hotdocs-criterion: sha256:eb3bcbc4b4d1ac32e44d9288d57b27490575faa345203764eec375225d13a6af
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

REQUIREMENT = (
    "# R-FOO-001\n"
    "\n"
    "**R-FOO-001** \u2014 `make_foo()` MUST return the string `\"foo\"`.\n"
)

LIBRARY = (
    "# Library\n"
    "\n"
    "One module file, `foo.py`.\n"
    "\n"
    "```\n"
    "make_foo() -> str\n"
    "```\n"
)

ACCEPTANCE_HEAD = (
    "# AC-FOO-001\n"
    "\n"
    "Covers: R-FOO-001\n"
)

KIND_LINE = "Kind: generated-test\n"

ACCEPTANCE_TAIL = (
    "\n"
    "```gherkin\n"
    "Given nothing\n"
    "When make_foo() is called\n"
    "Then the result is \"foo\"\n"
    "```\n"
)

CONSTRAINTS = (
    "# Foo \u2014 Non-Functional Constraints\n"
    "\n"
    "- **Pure.** No I/O.\n"
)

AC_REL = "specs/components/foo/acceptance/AC-FOO-001.md"


def write(root, rel, text):
    p = Path(root) / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def build_corpus(root, with_kind):
    write(root, "specs/product/foo.md", PRODUCT_FOO)
    write(root, "specs/components/foo/component.md", COMPONENT_MD)
    write(root, "specs/components/foo/requirements/R-FOO-001.md", REQUIREMENT)
    write(root, "specs/components/foo/interface/library.md", LIBRARY)
    ac = ACCEPTANCE_HEAD + (KIND_LINE if with_kind else "") + ACCEPTANCE_TAIL
    write(root, AC_REL, ac)
    write(root, "specs/components/foo/constraints.md", CONSTRAINTS)


def lint010_fails(findings):
    out = []
    for f in findings:
        if field(f, "rule_id") == "R-LINT-010" and field(f, "severity") == "fail":
            out.append(f)
    return out


def test_clean_corpus_has_no_r_lint_010(tmp_path):
    build_corpus(tmp_path, with_kind=True)
    report = spec_linter.lint(None, tmp_path)
    assert field(report, "hard_failures") == 0
    assert lint010_fails(field(report, "findings")) == []


def test_missing_kind_gives_fail_finding_for_r_lint_010(tmp_path):
    build_corpus(tmp_path, with_kind=True)
    assert spec_linter.lint(None, tmp_path).hard_failures == 0

    build_corpus(tmp_path, with_kind=False)
    report = spec_linter.lint(None, tmp_path)
    findings = field(report, "findings")
    hits = lint010_fails(findings)
    assert len(hits) >= 1, findings
    assert any("AC-FOO-001" in str(field(h, "file")) for h in hits), hits
    assert field(report, "hard_failures") >= 1


def test_missing_kind_cli_json_report_and_exit_code(tmp_path, capsys):
    build_corpus(tmp_path, with_kind=False)
    code = spec_linter.main(["--format=json", "--repo-root=" + str(tmp_path)])
    out = capsys.readouterr().out
    assert code == 1
    doc = json.loads(out)
    hits = [
        f for f in doc["findings"]
        if f["rule_id"] == "R-LINT-010" and f["severity"] == "fail"
    ]
    assert len(hits) >= 1, doc
    assert doc["summary"]["hard_failures"] >= 1