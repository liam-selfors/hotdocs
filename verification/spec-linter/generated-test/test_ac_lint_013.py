# hotdocs-criterion: sha256:61db05092eedaece4a105d794a4e5a5f88c37bb11c8c9b413667fcf00b28f624
import json
from pathlib import Path

import spec_linter


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _plain(value):
    return getattr(value, "value", value)


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

LIB_FOO = (
    "# Library\n"
    "\n"
    "One module file, `foo.py`.\n"
    "\n"
    "```\n"
    "make_foo() -> str\n"
    "```\n"
)

AC_FOO = (
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

CONSTRAINTS_FOO = (
    "# Foo \u2014 Non-Functional Constraints\n"
    "\n"
    "- **Pure.** No I/O.\n"
)


def _var_doc(with_default):
    text = (
        "---\n"
        "id: VAR-DB-PASSWORD\n"
        "title: Database password\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "---\n"
        "\n"
        "# VAR-DB-PASSWORD\n"
        "\n"
        "- name: VAR-DB-PASSWORD\n"
        "- required\n"
        "- type: secret-ref\n"
        "- description: The password used to connect to the database.\n"
        "- sensitivity: secret\n"
    )
    if with_default:
        text += "- default: hunter2\n"
    return text


def _write(root, rel, text):
    p = Path(root) / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def _build_corpus(root, with_default):
    _write(root, "specs/product/foo.md", PRODUCT_FOO)
    _write(root, "specs/components/foo/component.md", COMPONENT_FOO)
    _write(root, "specs/components/foo/requirements/R-FOO-001.md", REQ_FOO)
    _write(root, "specs/components/foo/interface/library.md", LIB_FOO)
    _write(root, "specs/components/foo/acceptance/AC-FOO-001.md", AC_FOO)
    _write(root, "specs/components/foo/constraints.md", CONSTRAINTS_FOO)
    _write(root, "specs/vars/db-password.md", _var_doc(with_default))


def _r013_findings(report):
    out = []
    for f in field(report, "findings"):
        if field(f, "rule_id") == "R-LINT-013":
            out.append(f)
    return out


def test_secret_var_with_default_fails_r_lint_013(tmp_path):
    _build_corpus(tmp_path, with_default=True)
    report = spec_linter.lint(None, tmp_path)
    findings = _r013_findings(report)
    fails = [f for f in findings if _plain(field(f, "severity")) == "fail"]
    assert fails, "expected a fail-severity R-LINT-013 finding, got: " + repr(
        field(report, "findings")
    )
    files = [str(field(f, "file")).replace("\\", "/") for f in fails]
    assert any(p.endswith("specs/vars/db-password.md") for p in files), repr(files)
    assert field(report, "hard_failures") >= 1


def test_secret_var_without_default_has_no_r_lint_013(tmp_path):
    _build_corpus(tmp_path, with_default=False)
    report = spec_linter.lint(None, tmp_path)
    assert _r013_findings(report) == []


def test_cli_reports_r_lint_013_fail_and_exits_1(tmp_path, capsys):
    _build_corpus(tmp_path, with_default=True)
    code = spec_linter.main(["--format=json", "--repo-root=" + str(tmp_path)])
    out = capsys.readouterr().out
    assert code == 1
    data = json.loads(out)
    matches = [
        f
        for f in data["findings"]
        if f["rule_id"] == "R-LINT-013" and f["severity"] == "fail"
    ]
    assert matches, repr(data)
    assert data["summary"]["hard_failures"] >= 1