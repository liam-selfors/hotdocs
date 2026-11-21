# hotdocs-criterion: sha256:661deafe920d07bf28fedeaee611c0ab668821ad17f63db22c611bf944690475
import spec_linter

from pathlib import Path


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


def component_md(extra_frontmatter=""):
    return (
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "depends_on: []\n"
        "realizes: [P-FOO]\n"
        "sealed: false\n"
        + extra_frontmatter
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


def build_corpus(repo_root, extra_frontmatter=""):
    write(repo_root / "specs" / "product" / "foo.md", PRODUCT_FOO)
    comp = repo_root / "specs" / "components" / "foo"
    write(comp / "component.md", component_md(extra_frontmatter))
    write(comp / "requirements" / "R-FOO-001.md", REQ)
    write(comp / "interface" / "library.md", LIBRARY)
    write(comp / "acceptance" / "AC-FOO-001.md", AC)
    write(comp / "constraints.md", CONSTRAINTS)


def test_clean_corpus_precondition(tmp_path):
    repo_root = tmp_path / "repo"
    build_corpus(repo_root)
    report = spec_linter.lint(None, repo_root)
    assert field(report, "hard_failures") == 0


def test_unresolved_depends_on_guarantees_entry_fails_r_lint_018(tmp_path):
    repo_root = tmp_path / "repo"
    build_corpus(repo_root, "depends_on_guarantees: [G-DOES-NOT-EXIST]\n")

    report = spec_linter.lint(None, repo_root)
    findings = list(field(report, "findings"))

    matching = [
        f
        for f in findings
        if field(f, "rule_id") == "R-LINT-018" and field(f, "severity") == "fail"
    ]
    assert matching, (
        "expected a fail-severity R-LINT-018 finding, got: "
        + repr([(field(f, "rule_id"), field(f, "severity"), field(f, "message")) for f in findings])
    )
    assert field(report, "hard_failures") >= 1