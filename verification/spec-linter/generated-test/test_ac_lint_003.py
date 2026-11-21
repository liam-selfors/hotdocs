# hotdocs-criterion: sha256:8b340cfbcb16680c94094e81955d375c6be8433fa6227f386e2beb4999536c55
import json
from pathlib import Path

import spec_linter


DANGLING_ID = "comp-ghost-nowhere"


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


def component_md(depends_on_line):
    return (
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [team-a]\n"
        + depends_on_line + "\n"
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

ACCEPTANCE = (
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


def build_corpus(repo_root, depends_on_line):
    specs = repo_root / "specs"
    write(specs / "product" / "foo.md", PRODUCT_FOO)
    comp = specs / "components" / "foo"
    write(comp / "component.md", component_md(depends_on_line))
    write(comp / "requirements" / "R-FOO-001.md", REQUIREMENT)
    write(comp / "interface" / "library.md", LIBRARY)
    write(comp / "acceptance" / "AC-FOO-001.md", ACCEPTANCE)
    write(comp / "constraints.md", CONSTRAINTS)


def r_lint_003_fails_naming(findings):
    matches = []
    for f in findings:
        if (
            field(f, "rule_id") == "R-LINT-003"
            and field(f, "severity") == "fail"
            and DANGLING_ID in str(field(f, "message"))
        ):
            matches.append(f)
    return matches


def test_clean_corpus_precondition(tmp_path):
    build_corpus(tmp_path, "depends_on: []")
    report = spec_linter.lint(None, tmp_path)
    assert field(report, "hard_failures") == 0


def test_dangling_depends_on_reports_r_lint_003_fail(tmp_path):
    build_corpus(tmp_path, "depends_on: []")
    assert field(spec_linter.lint(None, tmp_path), "hard_failures") == 0

    build_corpus(tmp_path, "depends_on: [" + DANGLING_ID + "]")
    report = spec_linter.lint(None, tmp_path)
    findings = list(field(report, "findings"))

    matches = r_lint_003_fails_naming(findings)
    assert matches, (
        "expected a fail-severity R-LINT-003 finding naming "
        + repr(DANGLING_ID)
        + ", got "
        + repr(findings)
    )
    assert field(report, "hard_failures") >= 1
    for f in matches:
        assert str(field(f, "file")).replace("\\", "/").endswith(
            "specs/components/foo/component.md"
        )


def test_dangling_depends_on_via_cli_json(tmp_path, capsys):
    build_corpus(tmp_path, "depends_on: [" + DANGLING_ID + "]")
    code = spec_linter.main(["--format=json", "--repo-root=" + str(tmp_path)])
    out = capsys.readouterr().out
    assert code == 1
    data = json.loads(out)
    matches = r_lint_003_fails_naming(data["findings"])
    assert matches, "no R-LINT-003 fail naming the dangling id in " + repr(data)
    assert data["summary"]["hard_failures"] >= 1