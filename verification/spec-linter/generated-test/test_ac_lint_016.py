# hotdocs-criterion: sha256:082a71183986398a469816cb1f512dff908cd018d5837ba7887a91bd3a4f0a43
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

REQUIREMENT_BODY = (
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

ACCEPTANCE_MD = (
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

CONSTRAINTS_MD = (
    "# Foo \u2014 Non-Functional Constraints\n"
    "\n"
    "- **Pure.** No I/O.\n"
)

FRONTMATTER = (
    "---\n"
    "id: R-FOO-001\n"
    "title: Foo returns foo\n"
    "status: draft\n"
    "---\n"
    "\n"
)

REQ_REL = "specs/components/foo/requirements/R-FOO-001.md"


def write(root, rel, text):
    p = Path(root) / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def build_clean_corpus(root):
    write(root, "specs/product/foo.md", PRODUCT_FOO)
    write(root, "specs/components/foo/component.md", COMPONENT_MD)
    write(root, REQ_REL, REQUIREMENT_BODY)
    write(root, "specs/components/foo/interface/library.md", LIBRARY_MD)
    write(root, "specs/components/foo/acceptance/AC-FOO-001.md", ACCEPTANCE_MD)
    write(root, "specs/components/foo/constraints.md", CONSTRAINTS_MD)


def r016_fail_findings(report):
    out = []
    for f in field(report, "findings"):
        if field(f, "rule_id") == "R-LINT-016" and field(f, "severity") == "fail":
            out.append(f)
    return out


def test_clean_corpus_has_no_r_lint_016(tmp_path):
    build_clean_corpus(tmp_path)
    report = spec_linter.lint(None, tmp_path)
    assert field(report, "hard_failures") == 0
    assert r016_fail_findings(report) == []


def test_requirement_with_frontmatter_fails_r_lint_016(tmp_path):
    build_clean_corpus(tmp_path)
    assert spec_linter.lint(None, tmp_path).hard_failures == 0

    write(tmp_path, REQ_REL, FRONTMATTER + REQUIREMENT_BODY)

    report = spec_linter.lint(None, tmp_path)
    hits = r016_fail_findings(report)
    assert hits, "expected a fail-severity R-LINT-016 finding, got: " + repr(
        [(field(f, "rule_id"), field(f, "severity"), field(f, "file")) for f in field(report, "findings")]
    )
    files = [str(field(f, "file")).replace("\\", "/") for f in hits]
    assert any(fl.endswith("requirements/R-FOO-001.md") for fl in files), repr(files)
    assert field(report, "hard_failures") >= 1


def test_requirement_with_frontmatter_cli_json_reports_r_lint_016(tmp_path, capsys):
    build_clean_corpus(tmp_path)
    write(tmp_path, REQ_REL, FRONTMATTER + REQUIREMENT_BODY)

    capsys.readouterr()
    code = spec_linter.main(["--format=json", "--repo-root=" + str(tmp_path)])
    out = capsys.readouterr().out
    assert code == 1
    data = json.loads(out)
    hits = [
        f for f in data["findings"]
        if f["rule_id"] == "R-LINT-016" and f["severity"] == "fail"
    ]
    assert hits, repr(data)
    assert any(
        str(f["file"]).replace("\\", "/").endswith("requirements/R-FOO-001.md") for f in hits
    ), repr(hits)
    assert data["summary"]["hard_failures"] >= 1