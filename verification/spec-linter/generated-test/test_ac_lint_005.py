# hotdocs-criterion: sha256:a157ab79c198320aed07dc80fec19a438ebbbf82e145e9dfbdd132f6d0f33d6e
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


def component_md(sealed_line):
    return (
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "depends_on: []\n"
        "realizes: [P-FOO]\n"
        + sealed_line
        + "---\n"
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


REQ = (
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

AC = (
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


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_corpus(repo_root, sealed_line):
    write(repo_root / "specs" / "product" / "foo.md", PRODUCT_FOO)
    comp = repo_root / "specs" / "components" / "foo"
    write(comp / "component.md", component_md(sealed_line))
    write(comp / "requirements" / "R-FOO-001.md", REQ)
    write(comp / "interface" / "library.md", LIBRARY)
    write(comp / "acceptance" / "AC-FOO-001.md", AC)
    write(comp / "constraints.md", CONSTRAINTS)


def r_lint_005_fails(findings):
    return [
        f
        for f in findings
        if field(f, "rule_id") == "R-LINT-005" and field(f, "severity") == "fail"
    ]


def test_clean_corpus_has_no_r_lint_005_finding(tmp_path):
    repo_root = tmp_path / "repo"
    build_corpus(repo_root, "sealed: false\n")
    report = spec_linter.lint(None, repo_root)
    findings = field(report, "findings")
    assert not [f for f in findings if field(f, "rule_id") == "R-LINT-005"]


def test_sealed_without_source_path_fails_r_lint_005_library(tmp_path):
    repo_root = tmp_path / "repo"
    build_corpus(repo_root, "sealed: true\n")
    text = (repo_root / "specs" / "components" / "foo" / "component.md").read_text()
    assert "source_path" not in text

    report = spec_linter.lint(None, repo_root)
    findings = field(report, "findings")
    matches = r_lint_005_fails(findings)
    assert matches, "expected a fail-severity R-LINT-005 finding, got: " + repr(findings)
    assert field(report, "hard_failures") >= 1


def test_sealed_without_source_path_fails_r_lint_005_cli(tmp_path, capsys):
    repo_root = tmp_path / "repo"
    build_corpus(repo_root, "sealed: true\n")

    code = spec_linter.main(["--format=json", "--repo-root=" + str(repo_root)])
    out = capsys.readouterr().out
    assert code == 1
    doc = json.loads(out)
    findings = doc["findings"]
    matches = r_lint_005_fails(findings)
    assert matches, "expected a fail-severity R-LINT-005 finding, got: " + repr(findings)
    assert doc["summary"]["hard_failures"] >= 1