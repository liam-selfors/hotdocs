# hotdocs-criterion: sha256:af8972e9e0ff7a1128e5c74f6e01be99e950cc4ace61288d1daf87b0d622e7f4
import io
import json
import contextlib
from pathlib import Path

import spec_linter


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


PRODUCT = (
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

COMPONENT = (
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

REQ_001 = (
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

AC_001 = (
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

CONSTRAINTS = (
    "# Foo \u2014 Non-Functional Constraints\n"
    "\n"
    "- **Pure.** No I/O.\n"
)


def write(root, rel, text):
    p = Path(root) / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def build_clean(root):
    write(root, "specs/product/foo.md", PRODUCT)
    write(root, "specs/components/foo/component.md", COMPONENT)
    write(root, "specs/components/foo/requirements/R-FOO-001.md", REQ_001)
    write(root, "specs/components/foo/interface/library.md", LIBRARY)
    write(root, "specs/components/foo/acceptance/AC-FOO-001.md", AC_001)
    write(root, "specs/components/foo/constraints.md", CONSTRAINTS)


def build_uncovered(root):
    build_clean(root)
    (Path(root) / "specs/components/foo/acceptance/AC-FOO-001.md").unlink()


def names_req(finding, req_id):
    message = str(field(finding, "message") or "")
    file = str(field(finding, "file") or "")
    return req_id in message or req_id in file


def lint_008_findings(report):
    return [f for f in field(report, "findings")
            if field(f, "rule_id") == "R-LINT-008"]


def test_clean_corpus_has_no_forward_traceability_failure(tmp_path):
    build_clean(tmp_path)
    report = spec_linter.lint(None, tmp_path)
    assert lint_008_findings(report) == []


def test_uncovered_requirement_yields_fail_finding(tmp_path):
    build_uncovered(tmp_path)
    report = spec_linter.lint(None, tmp_path)
    matches = [f for f in lint_008_findings(report)
               if field(f, "severity") == "fail" and names_req(f, "R-FOO-001")]
    assert matches, [
        (field(f, "rule_id"), field(f, "severity"), field(f, "file"),
         field(f, "message"))
        for f in field(report, "findings")
    ]
    assert field(report, "hard_failures") >= 1


def test_uncovered_requirement_only_named_requirement_flagged(tmp_path):
    build_uncovered(tmp_path)
    # A second, covered requirement must not be flagged.
    write(tmp_path, "specs/components/foo/requirements/R-FOO-002.md",
          "# R-FOO-002\n\n**R-FOO-002** \u2014 `make_foo()` MUST NOT raise.\n")
    write(tmp_path, "specs/components/foo/acceptance/AC-FOO-002.md",
          "# AC-FOO-002\n\nCovers: R-FOO-002\nKind: generated-test\n\n"
          "```gherkin\nGiven nothing\nWhen make_foo() is called\n"
          "Then nothing is raised\n```\n")
    report = spec_linter.lint(None, tmp_path)
    findings = lint_008_findings(report)
    assert any(field(f, "severity") == "fail" and names_req(f, "R-FOO-001")
               for f in findings)
    assert not any(names_req(f, "R-FOO-002") and not names_req(f, "R-FOO-001")
                   for f in findings)


def test_cli_json_reports_fail_and_exits_1(tmp_path):
    build_uncovered(tmp_path)
    out = io.StringIO()
    err = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = spec_linter.main(["--format=json", "--repo-root=" + str(tmp_path)])
    assert code == 1, err.getvalue()
    doc = json.loads(out.getvalue())
    matches = [f for f in doc["findings"]
               if f["rule_id"] == "R-LINT-008" and f["severity"] == "fail"
               and ("R-FOO-001" in str(f.get("message", ""))
                    or "R-FOO-001" in str(f.get("file", "")))]
    assert matches, doc
    assert doc["summary"]["hard_failures"] >= 1